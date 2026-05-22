from copy import deepcopy
from stream_transcribe import simple_dedup, fuzzy_boundary_dedup


def simulate_sequence(sequence_name, chunks, expectations=None):
    """
    Simulate the real pipeline at text level:

    chunk -> stage1(simple_dedup) -> stage2(fuzzy_boundary_dedup) -> append to clean history
    raw history just appends all chunks directly.

    expectations:
        dict with optional keys:
        - require_any_stage2_hit: bool
        - forbid_empty_clean_chunks: bool
        - required_clean_substrings: list[str]
        - forbidden_clean_substrings: list[str]
        - max_empty_clean_chunks: int
    """
    expectations = expectations or {}

    raw_history = []
    clean_history = []
    last_output_text = ""

    any_stage2_hit = False
    empty_clean_chunks = 0

    print(f"\n{'=' * 80}")
    print(f"SEQUENCE: {sequence_name}")
    print(f"{'=' * 80}")

    for idx, chunk in enumerate(chunks, start=1):
        print(f"\n--- Chunk {idx} ---")
        print("INPUT CHUNK:")
        print(chunk)

        raw_history.append(chunk)

        stage1 = simple_dedup(chunk, last_output_text)
        stage2 = fuzzy_boundary_dedup(last_output_text, stage1)

        s1_changed = (stage1 != chunk)
        s2_changed = (stage2 != stage1)

        if s2_changed:
            any_stage2_hit = True

        if not stage2.strip():
            empty_clean_chunks += 1
        else:
            if last_output_text:
                last_output_text += "\n" + stage2
            else:
                last_output_text = stage2
            clean_history.append(stage2)

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

    print(f"\n{'-' * 80}")
    print("RAW HISTORY")
    print(f"{'-' * 80}")
    print(raw_text)

    print(f"\n{'-' * 80}")
    print("CLEAN HISTORY")
    print(f"{'-' * 80}")
    print(clean_text)

    print(f"\n{'-' * 80}")
    print("METRICS")
    print(f"{'-' * 80}")
    print("Raw chars         :", raw_len)
    print("Clean chars       :", clean_len)
    print("Compression ratio :", f"{compression_ratio:.3f}")
    print("Any Stage2 hit    :", any_stage2_hit)
    print("Empty clean chunks:", empty_clean_chunks)

    checks = []

    if "require_any_stage2_hit" in expectations:
        checks.append((
            "require_any_stage2_hit",
            any_stage2_hit == expectations["require_any_stage2_hit"]
        ))

    if expectations.get("forbid_empty_clean_chunks", False):
        checks.append((
            "forbid_empty_clean_chunks",
            empty_clean_chunks == 0
        ))

    if "max_empty_clean_chunks" in expectations:
        checks.append((
            "max_empty_clean_chunks",
            empty_clean_chunks <= expectations["max_empty_clean_chunks"]
        ))

    for required in expectations.get("required_clean_substrings", []):
        checks.append((
            f"required_clean_substring::{required}",
            required in clean_text
        ))

    for forbidden in expectations.get("forbidden_clean_substrings", []):
        checks.append((
            f"forbidden_clean_substring::{forbidden}",
            forbidden not in clean_text
        ))

    all_pass = all(ok for _, ok in checks) if checks else True

    print(f"\n{'-' * 80}")
    print("CHECKS")
    print(f"{'-' * 80}")
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
        "any_stage2_hit": any_stage2_hit,
        "empty_clean_chunks": empty_clean_chunks,
        "passed": all_pass,
    }


def build_medium_interference_chunks():
    """
    Medium oral interference:
    - some filler
    - moderate repetition
    - moderate paraphrase
    - should mostly be handled
    """
    return [
        "[0.00s -> 4.20s] okay today we are going to talk about conditional independence\n"
        "[4.20s -> 8.10s] and the main idea is that two variables can be unrelated once you know a third variable",

        "[7.20s -> 11.00s] today we're going to talk about conditional independence\n"
        "[11.00s -> 15.20s] and the core idea is that two variables can be unrelated once a third variable is known",

        "[14.50s -> 18.40s] what this means is that knowing the third variable blocks the information path\n"
        "[18.40s -> 22.50s] so in practice this gives us a simpler way to reason about the graph",

        "[21.60s -> 25.40s] what this means is that once the third variable is known it blocks the path\n"
        "[25.40s -> 29.80s] and in practice this gives us a simpler way to reason about the graphical model",

        "[29.00s -> 32.80s] now let me give a very simple example\n"
        "[32.80s -> 36.70s] suppose weather affects whether the grass is wet and whether people carry umbrellas",

        "[35.80s -> 40.10s] let me give a simple example\n"
        "[40.10s -> 44.60s] suppose weather affects the wet grass and also affects whether people carry umbrellas",
    ]


def build_high_interference_chunks():
    """
    Higher oral interference:
    - more filler
    - more restart behavior
    - more repeated framing
    - stronger speaker noise
    Goal is not perfect cleanup, but substantial reduction of repeated boundary noise.
    """
    return [
        "[0.00s -> 3.60s] okay so um today I want to sort of talk about bayesian networks\n"
        "[3.60s -> 7.80s] and really the key point is that a graph gives us a compact way to represent dependencies",

        "[7.00s -> 10.40s] okay so today I want to talk about bayesian networks\n"
        "[10.40s -> 14.80s] and the key point really is that the graph gives us a compact way to represent probabilistic dependencies",

        "[14.10s -> 17.70s] and uh what I mean by that is you do not have to write the full joint distribution directly\n"
        "[17.70s -> 22.20s] instead you break the whole distribution into smaller local conditional pieces",

        "[21.60s -> 25.40s] what I mean is that you don't need to write the entire joint distribution directly\n"
        "[25.40s -> 30.20s] instead you break it into smaller local conditional distributions for each node",

        "[29.40s -> 33.20s] now okay let me say that one more time because this part matters\n"
        "[33.20s -> 37.60s] each node depends only on its parents rather than on every other variable in the system",

        "[36.80s -> 40.30s] let me say that again because this part is important\n"
        "[40.30s -> 44.90s] each node depends only on its parents and not on all the other variables in the graph",

        "[44.20s -> 48.10s] so if the graph is sparse the representation is much cheaper\n"
        "[48.10s -> 52.80s] and that is one reason these models are useful in practice",

        "[52.00s -> 55.90s] so if the graph is relatively sparse the representation is much cheaper\n"
        "[55.90s -> 60.70s] and that is part of the reason these models are useful in many practical settings",
    ]


def main():
    medium_expectations = {
        "require_any_stage2_hit": True,
        "max_empty_clean_chunks": 1,
        "required_clean_substrings": [
            "conditional independence",
            "simpler way to reason",
            "simple example",
        ],
        "forbidden_clean_substrings": [
            "today we're going to talk about conditional independence\n[11.00s -> 15.20s] and the core idea",
        ],
    }

    high_expectations = {
        "require_any_stage2_hit": True,
        "max_empty_clean_chunks": 2,
        "required_clean_substrings": [
            "bayesian networks",
            "compact way to represent",
            "local conditional",
            "depends only on its parents",
        ],
        # Not too strict: higher interference means some filler may remain.
        "forbidden_clean_substrings": [
            "okay so today I want to talk about bayesian networks\n[10.40s -> 14.80s] and the key point really is",
        ],
    }

    medium_result = simulate_sequence(
        "Medium oral interference sequence",
        build_medium_interference_chunks(),
        expectations=deepcopy(medium_expectations),
    )

    high_result = simulate_sequence(
        "High oral interference sequence",
        build_high_interference_chunks(),
        expectations=deepcopy(high_expectations),
    )

    print(f"\n{'=' * 80}")
    print("GLOBAL SUMMARY")
    print(f"{'=' * 80}")
    for result in [medium_result, high_result]:
        print(
            f"{result['sequence_name']}: "
            f"{'PASS' if result['passed'] else 'FAIL'} | "
            f"compression_ratio={result['compression_ratio']:.3f} | "
            f"any_stage2_hit={result['any_stage2_hit']} | "
            f"empty_clean_chunks={result['empty_clean_chunks']}"
        )


if __name__ == "__main__":
    main()