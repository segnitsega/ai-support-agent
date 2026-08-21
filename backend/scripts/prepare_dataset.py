"""
prepare_dataset.py

Filters the Bitext Customer Support CSV down to the intents that are
suitable for RAG (policy/how-to questions with a single correct answer),
excludes intents that need a real per-customer lookup or should route to
escalation, and writes the result as a JSONL file of chunks ready for
embedding.

Usage:
    python scripts/prepare_dataset.py \
        --input backend/data/raw/Bitext_Sample_Customer_Support_Training_Dataset_27K_responses-v11.csv \
        --output backend/data/faq_docs/support_faq.jsonl \
        --per-intent 6

Requires: pandas (pip install pandas)
"""

import argparse
import json
from pathlib import Path

import pandas as pd

# Intents that are pure policy/how-to knowledge — same answer for every
# customer, good fit for the RAG knowledge base.
RAG_INTENTS = {
    "recover_password",
    "registration_problems",
    "create_account",
    "edit_account",
    "delete_account",
    "switch_account",
    "check_cancellation_fee",
    "contact_customer_service",
    "delivery_options",
    "delivery_period",
    "review",
    "check_invoice",
    "newsletter_subscription",
    "place_order",
    "change_order",
    "check_payment_methods",
    "check_refund_policy",
    "set_up_shipping_address",
    "change_shipping_address",
}

# Intents that need a real per-customer lookup/action — these should be
# excluded from RAG and instead handled by a tool call in the graph.
# Kept here only as documentation / for building eval questions later.
TOOL_INTENTS = {
    "track_order",
    "cancel_order",
    "get_refund",
    "track_refund",
    "payment_issue",
    "get_invoice",
}

# Intents that should route straight to human escalation, not be answered.
ESCALATE_INTENTS = {
    "complaint",
    "contact_human_agent",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path to the raw Bitext CSV")
    parser.add_argument(
        "--output",
        default="backend/data/faq_docs/support_faq.jsonl",
        help="Path to write the filtered JSONL chunks",
    )
    parser.add_argument(
        "--per-intent",
        type=int,
        default=6,
        help="Max number of rows to keep per intent (default: 6)",
    )
    parser.add_argument(
        "--eval-output",
        default="backend/data/eval/eval_questions.jsonl",
        help="Path to write a held-out eval set (RAG + tool + escalate intents)",
    )
    parser.add_argument(
        "--eval-per-intent",
        type=int,
        default=2,
        help="Rows per intent to hold out for the eval set (default: 2)",
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    df = pd.read_csv(args.input)

    expected_cols = {"instruction", "response", "category", "intent"}
    missing = expected_cols - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing expected columns: {missing}")

    # --- Build the RAG chunk set ---
    rag_df = df[df["intent"].isin(RAG_INTENTS)]

    # NOTE: using groupby(...).apply(...) here would trip a pandas
    # version difference (newer pandas versions can drop the grouping
    # column from what's passed into the function). Looping over the
    # groups directly avoids that entirely and works the same across
    # pandas versions.
    sampled_parts = []
    for _, group in rag_df.groupby("intent"):
        n = min(len(group), args.per_intent)
        sampled_parts.append(group.sample(n, random_state=args.seed))
    sampled = pd.concat(sampled_parts).reset_index(drop=True) if sampled_parts else rag_df.iloc[0:0]

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for _, row in sampled.iterrows():
            chunk = {
                "text": f"Q: {row['instruction'].strip()}\nA: {row['response'].strip()}",
                "metadata": {
                    "intent": row["intent"],
                    "category": row["category"],
                },
            }
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    print(f"Wrote {len(sampled)} RAG chunks to {args.output}")
    print(f"Intents included ({len(RAG_INTENTS)}): {sorted(RAG_INTENTS)}")

    # --- Build a held-out eval set covering all three routing buckets ---
    all_routing_intents = RAG_INTENTS | TOOL_INTENTS | ESCALATE_INTENTS
    eval_df = df[df["intent"].isin(all_routing_intents)]

    # Exclude rows already used in the RAG chunk set so eval questions
    # are genuinely held out, not something already embedded.
    eval_df = eval_df[~eval_df.index.isin(sampled.index)] if not sampled.empty else eval_df

    eval_parts = []
    for _, group in eval_df.groupby("intent"):
        n = min(len(group), args.eval_per_intent)
        eval_parts.append(group.sample(n, random_state=args.seed))
    eval_sampled = pd.concat(eval_parts).reset_index(drop=True) if eval_parts else eval_df.iloc[0:0]

    def expected_route(intent: str) -> str:
        if intent in RAG_INTENTS:
            return "ANSWER_FROM_DOCS"
        if intent in TOOL_INTENTS:
            return "NEEDS_TOOL"
        return "ESCALATE"

    Path(args.eval_output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.eval_output, "w", encoding="utf-8") as f:
        for _, row in eval_sampled.iterrows():
            item = {
                "question": row["instruction"].strip(),
                "intent": row["intent"],
                "category": row["category"],
                "expected_route": expected_route(row["intent"]),
                "reference_answer": row["response"].strip(),
            }
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Wrote {len(eval_sampled)} eval questions to {args.eval_output}")


if __name__ == "__main__":
    main()