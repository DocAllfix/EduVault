"""Diagnostic isolated phase test for D.Lgs 81/08 ingest.

Esegue ogni fase separatamente con print espliciti per individuare DOVE
esattamente l'ingest precedente esplodeva con tenacity.RetryError.

Run from CONTAINER:
    docker compose exec -T backend python scripts/diag_ingest_dlgs81.py
"""
from __future__ import annotations

import asyncio
import sys
import traceback


async def main() -> None:
    pdf_path = "storage/pdfs/dlgs_81_08.pdf"

    # PHASE 1: PDF parsing
    print("=" * 70, flush=True)
    print("[PHASE 1] PDF parsing via pdfplumber", flush=True)
    print("=" * 70, flush=True)
    try:
        from app.services.ingestion_service import parse_regulation_pdf

        full_text = parse_regulation_pdf(pdf_path)
        print(f"  OK: {len(full_text):,} chars extracted", flush=True)
    except Exception as e:
        print(f"  EXPLODED here: {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)

    # PHASE 2: chunking
    print("=" * 70, flush=True)
    print("[PHASE 2] hybrid chunking", flush=True)
    print("=" * 70, flush=True)
    try:
        from app.services.ingestion_service import chunk_regulation

        chunks = chunk_regulation(full_text, "fake-id-for-diag")
        print(f"  OK: {len(chunks):,} chunks", flush=True)
        if chunks:
            sample = chunks[0]
            print(f"  Sample chunk body[:100]: {str(sample['body'])[:100]!r}", flush=True)
    except Exception as e:
        print(f"  EXPLODED here: {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)

    # PHASE 3: classify SOLO 1 chunk per testare provider
    print("=" * 70, flush=True)
    print("[PHASE 3] classify_chunk on 1 chunk (DeepSeek V4 Flash L0)", flush=True)
    print("=" * 70, flush=True)
    try:
        from app.services.ingestion_service import classify_chunk

        result = await classify_chunk(str(chunks[0]["body"]))
        print(f"  OK: {result}", flush=True)
    except BaseException as e:
        print(f"  EXPLODED here: {type(e).__name__}: {str(e)[:300]}", flush=True)
        traceback.print_exc()
        sys.exit(1)

    # PHASE 4: classify 5 chunks parallel (mini gather test)
    print("=" * 70, flush=True)
    print("[PHASE 4] classify 5 chunks in parallel", flush=True)
    print("=" * 70, flush=True)
    try:
        results = await asyncio.gather(
            *(classify_chunk(str(c["body"])) for c in chunks[:5]),
            return_exceptions=True,
        )
        ok = sum(1 for r in results if not isinstance(r, BaseException))
        fail = len(results) - ok
        print(f"  OK: {ok}/5 success, {fail}/5 failed", flush=True)
        for i, r in enumerate(results):
            if isinstance(r, BaseException):
                print(f"    chunk {i}: {type(r).__name__}: {str(r)[:200]}", flush=True)
    except Exception as e:
        print(f"  EXPLODED here: {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)

    # PHASE 5: embed_batch 1 doc (Voyage test)
    print("=" * 70, flush=True)
    print("[PHASE 5] embed_batch 1 doc via Voyage", flush=True)
    print("=" * 70, flush=True)
    try:
        from app.services.ingestion_service import embed_batch

        embs = await embed_batch([str(chunks[0]["body"])[:5000]])
        print(f"  OK: 1 embedding, dim={len(embs[0])}", flush=True)
    except BaseException as e:
        print(f"  EXPLODED here: {type(e).__name__}: {str(e)[:300]}", flush=True)
        traceback.print_exc()
        sys.exit(1)

    # PHASE 6: embed_batch 100 docs (medium batch)
    print("=" * 70, flush=True)
    print("[PHASE 6] embed_batch 100 docs via Voyage", flush=True)
    print("=" * 70, flush=True)
    try:
        sample_texts = [str(c["body"])[:5000] for c in chunks[:100]]
        embs = await embed_batch(sample_texts)
        print(f"  OK: {len(embs)} embeddings", flush=True)
    except BaseException as e:
        print(f"  EXPLODED here: {type(e).__name__}: {str(e)[:300]}", flush=True)
        traceback.print_exc()
        sys.exit(1)

    # PHASE 7: embed_batch 500 docs (target batch size in production)
    print("=" * 70, flush=True)
    print("[PHASE 7] embed_batch 500 docs via Voyage (production batch)", flush=True)
    print("=" * 70, flush=True)
    if len(chunks) >= 500:
        try:
            sample_texts = [str(c["body"])[:5000] for c in chunks[:500]]
            total_chars = sum(len(t) for t in sample_texts)
            print(f"  Total chars in batch: {total_chars:,}", flush=True)
            embs = await embed_batch(sample_texts)
            print(f"  OK: {len(embs)} embeddings", flush=True)
        except BaseException as e:
            print(f"  EXPLODED here: {type(e).__name__}: {str(e)[:300]}", flush=True)
            traceback.print_exc()
            sys.exit(1)
    else:
        print(f"  SKIP: only {len(chunks)} chunks total (< 500)", flush=True)

    print("=" * 70, flush=True)
    print("ALL PHASES OK — l'ingest pipeline funziona end-to-end", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
