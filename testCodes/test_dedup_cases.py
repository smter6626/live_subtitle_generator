from stream_transcribe import (
    simple_dedup,
    fuzzy_boundary_dedup,
    RAW_OUTPUT_FILE,
    CLEAN_OUTPUT_FILE,
)

def run_case(name, old_text, new_text):
    print(f"\n=== {name} ===")
    stage1 = simple_dedup(new_text, old_text)
    stage2 = fuzzy_boundary_dedup(old_text, stage1)

    print("OLD    :", old_text)
    print("NEW    :", new_text)
    print("STAGE1 :", repr(stage1))
    print("STAGE2 :", repr(stage2))

    changed_stage1 = (stage1 != new_text)
    changed_stage2 = (stage2 != stage1)

    print("S1 changed:", changed_stage1)
    print("S2 changed:", changed_stage2)

    return {
        "name": name,
        "stage1": stage1,
        "stage2": stage2,
        "changed_stage1": changed_stage1,
        "changed_stage2": changed_stage2,
    }


def main():
    print("RAW file  :", RAW_OUTPUT_FILE)
    print("CLEAN file:", CLEAN_OUTPUT_FILE)

    results = []

    # 1. 无重复：必须完全不动
    results.append(run_case(
        "No overlap",
        "[0.00s -> 2.00s] today we discuss bayesian networks",
        "[7.00s -> 9.00s] this is a completely new sentence",
    ))

    # 2. 精确重复：应由 simple_dedup 命中
    results.append(run_case(
        "Exact overlap",
        "[0.00s -> 2.00s] today we discuss bayesian networks",
        "[7.00s -> 9.00s] discuss bayesian networks and conditional probability",
    ))

    # 3. 完全重复：应被删空
    results.append(run_case(
        "Full overlap",
        "[0.00s -> 4.00s] this is exactly the same sentence",
        "[7.00s -> 11.00s] this is exactly the same sentence",
    ))

    # 4. 关键测试：we will vs we'll
    results.append(run_case(
        "Fuzzy overlap - will contraction",
        "[0.00s -> 4.00s] today we will discuss bayesian networks and conditional independence",
        "[7.00s -> 11.00s] today we'll discuss bayesian networks and conditional independence in detail",
    ))

    # 5. 关键测试：we are vs we're
    results.append(run_case(
        "Fuzzy overlap - are contraction",
        "[0.00s -> 4.00s] we are going to analyze the first part of the algorithm",
        "[7.00s -> 11.00s] we're going to analyze the first part of the algorithm step by step",
    ))

    # 6. 关键测试：do not vs don't
    results.append(run_case(
        "Fuzzy overlap - negation contraction",
        "[0.00s -> 4.00s] do not assume the variables are independent in this example",
        "[7.00s -> 11.00s] don't assume the variables are independent in this example yet",
    ))

    # 7. 不应误删：相似但不是重复
    results.append(run_case(
        "Should not trim - similar but different",
        "[0.00s -> 4.00s] we need more data to support the claim",
        "[7.00s -> 11.00s] we need more evidence to revise the claim",
    ))

    # 8. 不应误删：只有开头套话相似
    results.append(run_case(
        "Should not trim - common filler",
        "[0.00s -> 4.00s] I think this is the correct definition for the first case",
        "[7.00s -> 11.00s] I think we should move to the second example now",
    ))

    # 9. 不应误删：尾部不同实体
    results.append(run_case(
        "Should not trim - entity changed",
        "[0.00s -> 4.00s] today we discuss support vector machines in detail",
        "[7.00s -> 11.00s] today we discuss bayesian networks in detail",
    ))

    print("\n=== Summary ===")
    for r in results:
        print(
            f"{r['name']}: "
            f"S1_changed={r['changed_stage1']} "
            f"S2_changed={r['changed_stage2']} "
            f"Final={repr(r['stage2'])}"
        )


if __name__ == "__main__":
    main()