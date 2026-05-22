from stream_transcribe import simple_dedup, fuzzy_boundary_dedup


def simulate_sequence(sequence_name, chunks, expectations=None):
    expectations = expectations or {}

    raw_history = []
    clean_history = []
    last_output_text = ""

    stage1_hits = 0
    stage2_hits = 0
    empty_clean_chunks = 0

    print(f"\n{'=' * 90}")
    print(f"SEQUENCE: {sequence_name}")
    print(f"{'=' * 90}")

    for idx, chunk in enumerate(chunks, start=1):
        print(f"\n--- Chunk {idx} ---")
        print("INPUT CHUNK:")
        print(chunk)

        raw_history.append(chunk)

        stage1 = simple_dedup(chunk, last_output_text)
        stage2 = fuzzy_boundary_dedup(last_output_text, stage1)

        s1_changed = (stage1 != chunk)
        s2_changed = (stage2 != stage1)

        if s1_changed:
            stage1_hits += 1
        if s2_changed:
            stage2_hits += 1

        if stage2.strip():
            clean_history.append(stage2)
            if last_output_text:
                last_output_text += "\n" + stage2
            else:
                last_output_text = stage2
        else:
            empty_clean_chunks += 1

        print("STAGE1:")
        print(repr(stage1))
        print("STAGE2:")
        print(repr(stage2))
        print("S1 changed:", s1_changed)
        print("S2 changed:", s2_changed)

    raw_text = "\n".join(raw_history)
    clean_text = "\n".join(clean_history)

    raw_len = len(raw_text)
    clean_len = len(clean_text)
    compression_ratio = (clean_len / raw_len) if raw_len else 0.0

    print(f"\n{'-' * 90}")
    print("RAW HISTORY")
    print(f"{'-' * 90}")
    print(raw_text)

    print(f"\n{'-' * 90}")
    print("CLEAN HISTORY")
    print(f"{'-' * 90}")
    print(clean_text)

    print(f"\n{'-' * 90}")
    print("METRICS")
    print(f"{'-' * 90}")
    print("Raw chars         :", raw_len)
    print("Clean chars       :", clean_len)
    print("Compression ratio :", f"{compression_ratio:.3f}")
    print("Stage1 hits       :", stage1_hits)
    print("Stage2 hits       :", stage2_hits)
    print("Empty clean chunks:", empty_clean_chunks)

    checks = []

    min_stage1_hits = expectations.get("min_stage1_hits")
    if min_stage1_hits is not None:
        checks.append(("min_stage1_hits", stage1_hits >= min_stage1_hits))

    min_stage2_hits = expectations.get("min_stage2_hits")
    if min_stage2_hits is not None:
        checks.append(("min_stage2_hits", stage2_hits >= min_stage2_hits))

    max_compression_ratio = expectations.get("max_compression_ratio")
    if max_compression_ratio is not None:
        checks.append(("max_compression_ratio", compression_ratio <= max_compression_ratio))

    max_empty_clean_chunks = expectations.get("max_empty_clean_chunks")
    if max_empty_clean_chunks is not None:
        checks.append(("max_empty_clean_chunks", empty_clean_chunks <= max_empty_clean_chunks))

    for required in expectations.get("required_clean_substrings", []):
        checks.append((f"required::{required}", required in clean_text))

    for forbidden in expectations.get("forbidden_clean_substrings", []):
        checks.append((f"forbidden::{forbidden}", forbidden not in clean_text))

    all_pass = all(ok for _, ok in checks) if checks else True

    print(f"\n{'-' * 90}")
    print("CHECKS")
    print(f"{'-' * 90}")
    for label, ok in checks:
        print(f"{label}: {'PASS' if ok else 'FAIL'}")

    print("\nSEQUENCE RESULT:", "PASS" if all_pass else "FAIL")

    return {
        "sequence_name": sequence_name,
        "raw_text": raw_text,
        "clean_text": clean_text,
        "raw_len": raw_len,
        "clean_len": clean_len,
        "compression_ratio": compression_ratio,
        "stage1_hits": stage1_hits,
        "stage2_hits": stage2_hits,
        "empty_clean_chunks": empty_clean_chunks,
        "passed": all_pass,
    }


def build_medium_boundary_chunks():
    """
    Medium interference:
    - boundary overlap is clear
    - some contraction
    - some mild lexical variation
    - limited filler
    """
    return [
        "[0.00s -> 4.10s] today we are going to talk about conditional independence\n"
        "[4.10s -> 8.20s] the main idea is that two variables can become unrelated once a third variable is known",

        "[7.00s -> 10.80s] today we're going to talk about conditional independence\n"
        "[10.80s -> 15.30s] the core idea is that two variables can become unrelated once a third variable is known in the model",

        "[14.20s -> 18.10s] once a third variable is known the information path is blocked\n"
        "[18.10s -> 22.40s] and this gives us a simpler way to reason about the graph",

        "[21.20s -> 25.30s] once the third variable is known the path is blocked\n"
        "[25.30s -> 29.70s] and this gives us a simpler way to reason about the graphical model in practice",

        "[28.70s -> 32.20s] now let me give a simple example\n"
        "[32.20s -> 36.90s] suppose weather affects wet grass and also affects whether people carry umbrellas",

        "[35.80s -> 39.40s] let me give a very simple example\n"
        "[39.40s -> 44.20s] suppose weather affects the wet grass and affects whether people carry umbrellas in daily life",
    ]


def build_high_boundary_chunks():
    """
    Higher interference:
    - more filler
    - boundary overlap still exists
    - more restarts inside boundary region
    - should still allow some stage1/stage2 hits
    """
    return [
        "[0.00s -> 3.80s] okay so today I want to talk about bayesian networks\n"
        "[3.80s -> 8.20s] the key point is that a graph gives us a compact way to represent dependencies",

        "[7.00s -> 10.90s] okay so today I want to talk about bayesian networks\n"
        "[10.90s -> 15.60s] the key point really is that the graph gives us a compact way to represent probabilistic dependencies",

        "[14.70s -> 18.40s] this means you do not need to write the full joint distribution directly\n"
        "[18.40s -> 22.80s] instead you break the whole distribution into smaller local conditional pieces",

        "[21.90s -> 25.90s] what this means is that you don't need to write the entire joint distribution directly\n"
        "[25.90s -> 30.60s] instead you break it into smaller local conditional distributions for each node",

        "[29.70s -> 33.60s] let me say that again because this part is important\n"
        "[33.60s -> 38.20s] each node depends only on its parents rather than on every other variable in the graph",

        "[37.20s -> 41.00s] let me say that again because this part really matters\n"
        "[41.00s -> 45.90s] each node depends only on its parents and not on all the other variables in the full system",

        "[45.00s -> 48.90s] if the graph is sparse the representation becomes much cheaper\n"
        "[48.90s -> 53.40s] and that is one reason these models are useful in practice",

        "[52.40s -> 56.50s] if the graph is relatively sparse the representation becomes much cheaper\n"
        "[56.50s -> 61.20s] and that is part of the reason these models are useful in many practical settings",
    ]


def main():
    medium_expectations = {
        # 中等干扰下，应该至少有一定压缩和一定命中
        "min_stage1_hits": 1,
        "min_stage2_hits": 1,
        "max_compression_ratio": 0.92,
        "max_empty_clean_chunks": 1,
        "required_clean_substrings": [
            "conditional independence",
            "simpler way to reason",
            "simple example",
            "weather affects",
        ],
    }

    high_expectations = {
        # 高干扰下不要求很强压缩，但应该至少处理掉一部分
        "min_stage1_hits": 1,
        "min_stage2_hits": 1,
        "max_compression_ratio": 0.96,
        "max_empty_clean_chunks": 2,
        "required_clean_substrings": [
            "bayesian networks",
            "compact way to represent",
            "local conditional",
            "depends only on its parents",
            "representation becomes much cheaper",
        ],
    }

    medium_result = simulate_sequence(
        "Medium boundary-overlap sequence",
        build_medium_boundary_chunks(),
        medium_expectations,
    )

    high_result = simulate_sequence(
        "High boundary-overlap sequence",
        build_high_boundary_chunks(),
        high_expectations,
    )

    print(f"\n{'=' * 90}")
    print("GLOBAL SUMMARY")
    print(f"{'=' * 90}")
    for result in [medium_result, high_result]:
        print(
            f"{result['sequence_name']}: "
            f"{'PASS' if result['passed'] else 'FAIL'} | "
            f"compression_ratio={result['compression_ratio']:.3f} | "
            f"stage1_hits={result['stage1_hits']} | "
            f"stage2_hits={result['stage2_hits']} | "
            f"empty_clean_chunks={result['empty_clean_chunks']}"
        )


if __name__ == "__main__":
    main()