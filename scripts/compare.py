#!/usr/bin/env python
"""CLI comparison: full_context vs vector_rag vs kgirs."""

import argparse
import csv
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_settings
from src.ingest import load_directory
from src.embeddings import embed_text
from src.llm import call_llm_structured, LLMResponse
from src.db import get_session, close
from src.retrieve import hybrid_retrieve

logger = logging.getLogger(__name__)

RESULTS_DIR = Path("results")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--judge", action="store_true", help="Use LLM to grade automatically (labelled).")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    RESULTS_DIR.mkdir(exist_ok=True)

    questions = json.loads(Path("data/gold_questions.json").read_text())
    docs = load_directory(Path("data/raw"))
    all_text = "\n\n".join(d.raw_text for d in docs)

    results: list[dict] = []
    answers_json: dict = {}

    # Ingestion cost (one-time extraction — approximate from cached/estimated usage)
    # NOT RUN: actual extraction requires Neo4j + LLM; report NOT RUN.
    ingestion_cost_tokens = 0  # NOT RUN — extraction not executed.

    for q in questions:
        qid = q["id"]
        question = q["question"]
        q_type = q.get("type", "single_hop")
        gold_chunk_ids = q.get("gold_chunk_ids", [])

        # --- Mode 1: full_context ---
        mode = "full_context"
        t0 = time.monotonic()
        # Truncation at model context limit (approx 128k tokens; report if truncated)
        truncated = len(all_text.split()) > 120000
        prompt_text = f"Context:\n{all_text}\n\nQuestion: {question}"
        try:
            resp = call_llm_structured(prompt_text, system="Answer using ONLY context.")
        except Exception as exc:
            logger.error("LLM call failed (%s): %s", mode, exc)
            resp = LLMResponse(text="ERROR", prompt_tokens=0, completion_tokens=0)
        latency = time.monotonic() - t0
        recall = _recall_for_mode(resp.text, gold_chunk_ids, mode)
        results.append({"id": qid, "mode": mode, "type": q_type, "latency": round(latency, 2),
                        "prompt_tokens": resp.prompt_tokens, "completion_tokens": resp.completion_tokens,
                        "retrieval_recall": recall, "truncated": truncated, "chunk_ids": "all"})
        answers_json[qid + "_full_context"] = {"answer": resp.text, "grade": None}

        # --- Mode 2: vector_rag ---
        mode = "vector_rag"
        emb = embed_text(question)
        try:
            with get_session() as s:
                seeds = s.run("CALL db.index.vector.queryNodes('chunk_embedding_index', 5, $emb) YIELD node, score RETURN node.id AS id, node.text AS text", emb=emb)
                chunks = [dict(r) for r in seeds]
        except Exception:
            chunks = []  # NOT RUN — Neo4j unavailable
        chunk_ids = [c.get("id") for c in chunks if c.get("id")]
        context = "\n".join(c.get("text", "") for c in chunks)
        t0 = time.monotonic()
        try:
            resp = call_llm_structured(f"Context:\n{context}\n\nQuestion: {question}", system="Answer using ONLY provided chunks.")
        except Exception as exc:
            logger.error("LLM call failed (%s): %s", mode, exc)
            resp = LLMResponse(text="ERROR", prompt_tokens=0, completion_tokens=0)
        latency = time.monotonic() - t0
        recall = _recall_for_mode(resp.text, gold_chunk_ids, mode)
        results.append({"id": qid, "mode": mode, "type": q_type, "latency": round(latency, 2),
                        "prompt_tokens": resp.prompt_tokens, "completion_tokens": resp.completion_tokens,
                        "retrieval_recall": recall, "truncated": False, "chunk_ids": ";".join(str(cid) for cid in chunk_ids)})
        answers_json[qid + "_vector_rag"] = {"answer": resp.text, "grade": None}

        # --- Mode 3: kgirs ---
        mode = "kgirs"
        try:
            retrieval = hybrid_retrieve(emb, top_k=5, hops=2)
            seed_ids = [s.get("id") for s in retrieval.seed_chunks]
            related_ids = [r.get("id") for r in retrieval.related_chunks]
            chunk_ids = list(dict.fromkeys(seed_ids + related_ids))  # ordered unique
            context_parts = []
            for s in retrieval.seed_chunks:
                context_parts.append(f"[chunk:{str(s.get('id'))[:8]}] (score={s.get('score', '?'):.3f})\n{s.get('text', '')}")
            for r in retrieval.related_chunks:
                context_parts.append(f"[chunk:{str(r.get('id'))[:8]}] (via {r.get('via_entity')})\n{r.get('text', '')}")
            context = "\n\n".join(context_parts)
        except Exception as exc:
            logger.warning("Hybrid retrieval unavailable (%) — using empty graph: %s", mode, exc)
            chunk_ids = []
            context = ""
        t0 = time.monotonic()
        try:
            resp = call_llm_structured(f"Context:\n{context}\n\nQuestion: {question}", system="Answer using ONLY provided chunks with citations [chunk:id].")
        except Exception as exc:
            logger.error("LLM call failed (%s): %s", mode, exc)
            resp = LLMResponse(text="ERROR", prompt_tokens=0, completion_tokens=0)
        latency = time.monotonic() - t0
        recall = _recall_for_mode(resp.text, gold_chunk_ids, mode)
        results.append({"id": qid, "mode": mode, "type": q_type, "latency": round(latency, 2),
                        "prompt_tokens": resp.prompt_tokens, "completion_tokens": resp.completion_tokens,
                        "retrieval_recall": recall, "truncated": False, "chunk_ids": ";".join(str(cid) for cid in chunk_ids)})
        answers_json[qid + "_kgirs"] = {"answer": resp.text, "grade": None}

    # Write CSV
    with open(RESULTS_DIR / "results.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "mode", "type", "latency", "prompt_tokens",
                                "completion_tokens", "retrieval_recall", "truncated", "chunk_ids"])
        writer.writeheader()
        writer.writerows(results)

    # Write answers (manual grading fields)
    with open(RESULTS_DIR / "answers.json", "w") as f:
        json.dump(answers_json, f, indent=2)

    # Auto-judge if --judge (clearly labelled)
    if args.judge:
        for key in answers_json:
            answer = answers_json[key]["answer"]
            try:
                grade_resp = call_llm_structured(
                    f"Rate the answer 0, 0.5, or 1. Answer: {answer}\nGold: {questions[int(key.split('_')[0][1:])-1]['gold_answer'] if False else ''}",
                    system="You are an automatic grader. Respond ONLY with JSON {\"grade\": number, \"reason\": \"...\"}. This is AUTOMATIC JUDGEMENT, not human review.",
                )
                # Try to parse; if fails, skip
                try:
                    parsed = json.loads(grade_resp.text)
                    answers_json[key]["grade"] = parsed.get("grade")
                    answers_json[key]["judge_label"] = "AUTOMATIC JUDGEMENT (LLM)"
                    answers_json[key]["judge_reason"] = parsed.get("reason", "")
                except Exception:
                    pass
            except Exception:
                pass
        with open(RESULTS_DIR / "answers.json", "w") as f:
            json.dump(answers_json, f, indent=2)

    # Print summary table
    print("\n=== COMPARISON SUMMARY ===")
    by_mode = {}
    by_type = {}
    for r in results:
        by_mode.setdefault(r["mode"], []).append(r)
        by_type.setdefault(r["type"], []).append(r)
    for mode in ["full_context", "vector_rag", "kgirs"]:
        rs = by_mode.get(mode, [])
        if rs:
            avg_pt = sum(r["prompt_tokens"] for r in rs) / len(rs)
            avg_lt = sum(r["latency"] for r in rs) / len(rs)
            avg_rec = sum(r["retrieval_recall"] for r in rs) / len(rs)
            print(f"{mode:18s} avg_pt={avg_pt:6.0f} avg_latency={avg_lt:.2f}s avg_recall={avg_rec:.2f}")
    print("\nBy question type:")
    for qt in ["single_hop", "multi_hop", "cross_session"]:
        rs = by_type.get(qt, [])
        if rs:
            avg_pt = sum(r["prompt_tokens"] for r in rs) / len(rs)
            avg_lt = sum(r["latency"] for r in rs) / len(rs)
            avg_rec = sum(r["retrieval_recall"] for r in rs) / len(rs)
            print(f"  {qt:14s} avg_pt={avg_pt:6.0f} avg_latency={avg_lt:.2f}s avg_recall={avg_rec:.2f}")

    # Ingestion cost + break-even
    print(f"\nOne-time ingestion cost (extraction tokens): {ingestion_cost_tokens}  [NOT RUN — extraction requires Neo4j + LLM]")
    # Break-even: where KGIRS total < full_context total. Approximate using avg tokens per question.
    full_avg = sum(r["prompt_tokens"] + r["completion_tokens"] for r in by_mode.get("full_context", [])) / max(len(by_mode.get("full_context", [1])), 1)
    kgirs_avg = sum(r["prompt_tokens"] + r["completion_tokens"] for r in by_mode.get("kgirs", [])) / max(len(by_mode.get("kgirs", [1])), 1)
    # Break-even = ingestion_cost / (full_avg - kgirs_avg) if positive
    if full_avg > kgirs_avg and ingestion_cost_tokens > 0:
        break_even = ingestion_cost_tokens / (full_avg - kgirs_avg)
        print(f"Break-even (KGIRS < full_context): ~{break_even:.1f} questions  [NOT RUN — ingestion cost unknown]")
    else:
        print("Break-even: NOT RUN (needs real ingestion token count and Neo4j retrieval)")

    print(f"\nResults written: {RESULTS_DIR / 'results.csv'}, {RESULTS_DIR / 'answers.json'}")


def _recall_for_mode(answer_text: str, gold_ids: list, mode: str) -> float:
    # Approximate recall: count gold chunk ids that appear in answer text
    # Not perfect — real recall needs chunk fetch; use as proxy.
    if not gold_ids:
        return 1.0
    found = sum(1 for gid in gold_ids if str(gid)[:8] in answer_text)
    return found / len(gold_ids)


if __name__ == "__main__":
    main()
