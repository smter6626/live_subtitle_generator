from stream_transcribe import simple_dedup, fuzzy_boundary_dedup


def simulate_sequence(sequence_name, chunks, expectations=None):
    expectations = expectations or {}

    raw_history = []
    clean_history = []
    last_output_text = ""

    stage1_hits = 0
    stage2_hits = 0
    empty_clean_chunks = 0

    print(f"\n{'=' * 96}")
    print(f"SEQUENCE: {sequence_name}")
    print(f"{'=' * 96}")

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

    print(f"\n{'-' * 96}")
    print("RAW HISTORY")
    print(f"{'-' * 96}")
    print(raw_text)

    print(f"\n{'-' * 96}")
    print("CLEAN HISTORY")
    print(f"{'-' * 96}")
    print(clean_text)

    print(f"\n{'-' * 96}")
    print("METRICS")
    print(f"{'-' * 96}")
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

    print(f"\n{'-' * 96}")
    print("CHECKS")
    print(f"{'-' * 96}")
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


def build_medium_boundary_chunks_v3():
    """
    Medium interference:
    - overlap starts at the FIRST line of each new chunk
    - some contraction
    - some light lexical variation
    - limited filler
    """
    return [
        "[0.00s -> 4.20s] conditional independence means two variables can become unrelated once a third variable is known\n"
        "[4.20s -> 8.50s] once a third variable is known the information path is blocked in the graph",

        "[7.30s -> 11.10s] once the third variable is known the information path is blocked in the graph\n"
        "[11.10s -> 15.60s] and this gives us a simpler way to reason about the probabilistic model",

        "[14.40s -> 18.30s] this gives us a simpler way to reason about the probabilistic model\n"
        "[18.30s -> 22.70s] now let me give a simple example with weather wet grass and umbrellas",

        "[21.50s -> 25.10s] let me give a very simple example with weather wet grass and umbrellas\n"
        "[25.10s -> 29.80s] if weather is known then wet grass gives less extra information about umbrellas",

        "[28.60s -> 32.40s] if the weather is known then wet grass gives less extra information about umbrellas\n"
        "[32.40s -> 37.10s] so conditional independence reduces the number of dependencies we need to consider",

        "[35.90s -> 40.00s] conditional independence reduces the number of dependencies we need to consider\n"
        "[40.00s -> 44.80s] and that is why the graphical structure becomes easier to analyze in practice",
    ]


def build_high_boundary_chunks_v3():
    """
    Higher oral interference:
    - overlap still starts at first line
    - more filler / spoken style
    - more contractions
    - mild paraphrase, but still boundary-local
    """
    return [
        "[0.00s -> 4.10s] okay bayesian networks give us a compact way to represent probabilistic dependencies\n"
        "[4.10s -> 8.60s] the graph structure tells us which variables directly depend on which other variables",

        "[7.40s -> 11.20s] okay bayesian networks give us a compact way to represent dependencies\n"
        "[11.20s -> 15.90s] and the graph structure tells us which variables directly depend on other variables in the model",

        "[14.70s -> 18.50s] the graph structure tells us which variables directly depend on other variables in the model\n"
        "[18.50s -> 23.20s] so you do not need to write the full joint distribution directly from scratch",

        "[22.00s -> 26.00s] so you don't need to write the entire joint distribution directly from scratch\n"
        "[26.00s -> 30.70s] instead you break it into smaller local conditional distributions for each node",

        "[29.50s -> 33.40s] instead you break it into smaller local conditional distributions for each node\n"
        "[33.40s -> 38.30s] and each node depends only on its parents rather than on every variable in the system",

        "[37.10s -> 41.10s] each node depends only on its parents and not on every variable in the full system\n"
        "[41.10s -> 45.90s] so if the graph is sparse the representation becomes much cheaper in practice",

        "[44.70s -> 48.60s] if the graph is sparse the representation becomes much cheaper in practice\n"
        "[48.60s -> 53.50s] and that is one reason these models are useful for reasoning and computation",

        "[52.30s -> 56.20s] these models are useful for reasoning and computation in practice\n"
        "[56.20s -> 61.00s] because the graph lets us store structure without writing every dependency explicitly",
    ]


def main():
    medium_expectations = {
        # 中等干扰下：应明显有去重收益
        "min_stage1_hits": 1,
        "min_stage2_hits": 1,
        "max_compression_ratio": 0.90,
        "max_empty_clean_chunks": 1,
        "required_clean_substrings": [
            "conditional independence",
            "simpler way to reason",
            "weather",
            "dependencies we need to consider",
            "graphical structure",
        ],
    }

    high_expectations = {
        # 高干扰下：仍应处理掉一部分边界重复
        "min_stage1_hits": 1,
        "min_stage2_hits": 1,
        "max_compression_ratio": 0.94,
        "max_empty_clean_chunks": 2,
        "required_clean_substrings": [
            "bayesian networks",
            "compact way to represent",
            "full joint distribution",
            "local conditional distributions",
            "depends only on its parents",
            "representation becomes much cheaper",
            "reasoning and computation",
        ],
    }

    medium_result = simulate_sequence(
        "Medium precise-boundary sequence v3",
        build_medium_boundary_chunks_v3(),
        medium_expectations,
    )

    high_result = simulate_sequence(
        "High precise-boundary sequence v3",
        build_high_boundary_chunks_v3(),
        high_expectations,
    )

    print(f"\n{'=' * 96}")
    print("GLOBAL SUMMARY")
    print(f"{'=' * 96}")
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