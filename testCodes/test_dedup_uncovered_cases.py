from stream_transcribe import simple_dedup, fuzzy_boundary_dedup


def run_case(name, old_text, new_text):
    print(f"\n=== {name} ===")
    stage1 = simple_dedup(new_text, old_text)
    stage2 = fuzzy_boundary_dedup(old_text, stage1)

    print("OLD:")
    print(old_text)
    print("NEW:")
    print(new_text)
    print("STAGE1:")
    print(repr(stage1))
    print("STAGE2:")
    print(repr(stage2))
    print("S1 changed:", stage1 != new_text)
    print("S2 changed:", stage2 != stage1)

    return {
        "name": name,
        "stage1": stage1,
        "stage2": stage2,
        "changed_stage1": stage1 != new_text,
        "changed_stage2": stage2 != stage1,
    }


def main():
    results = []

    # 1) 真正偏 fuzzy 的轻微改写：不是简单 contraction
    #    目标：S1 不变，S2 最好发生裁剪；至少要看到 fuzzy debug 或 fuzzy hit
    results.append(run_case(
        "Fuzzy needed - lexical variation 1",
        "[0.00s -> 4.00s] today we discuss the basic idea of probabilistic graphical models",
        "[7.00s -> 11.00s] today we discuss the core idea of probabilistic graphical models in class",
    ))

    # 2) 真正偏 fuzzy：一个词替换 + 尾部扩展
    results.append(run_case(
        "Fuzzy needed - lexical variation 2",
        "[0.00s -> 4.00s] this example shows the relationship between the variables very clearly",
        "[7.00s -> 11.00s] this example shows the connection between the variables very clearly here",
    ))

    # 3) 词形变化 / 轻微改写，不该靠 contraction 吃掉
    results.append(run_case(
        "Fuzzy needed - wording shift",
        "[0.00s -> 4.00s] we can compute the value by using dynamic programming",
        "[7.00s -> 11.00s] we can calculate the value by using dynamic programming step by step",
    ))

    # 4) 多行 chunk：第二行开头重复，检查跨行处理
    results.append(run_case(
        "Multiline - overlap at second line start",
        "[0.00s -> 2.00s] today we start with the first definition\n"
        "[2.00s -> 4.00s] conditional independence is very important in this model",
        "[7.00s -> 9.00s] conditional independence is extremely important in this model for inference\n"
        "[9.00s -> 11.00s] then we move to the next example",
    ))

    # 5) 多行 chunk：第一行内部裁剪后应保留第一行 timestamp
    #    目标：如果裁剪发生在第一行内部，结果仍应带 [7.00s -> ...] 时间戳
    results.append(run_case(
        "Timestamp preserve - trim inside first line",
        "[0.00s -> 4.00s] bayesian networks are useful for representing uncertainty",
        "[7.00s -> 11.00s] networks are useful for representing uncertainty in many tasks\n"
        "[11.00s -> 14.00s] and now we discuss inference",
    ))

    # 6) 跨行 overlap：old 末行 vs new 首行
    results.append(run_case(
        "Cross-line boundary overlap",
        "[0.00s -> 2.00s] we now turn to the next topic\n"
        "[2.00s -> 4.00s] the first assumption is that the variables are independent",
        "[7.00s -> 9.00s] the first assumption is that the variables are mostly independent\n"
        "[9.00s -> 11.00s] this is not always true in practice",
    ))

    # 7) near miss：应尽量不裁，但希望触发 fuzzy debug
    #    目标：S2 不改，控制台若出现 best_near_match 更好
    results.append(run_case(
        "Near miss - debug candidate expected",
        "[0.00s -> 4.00s] the result depends on the distribution of the hidden variable",
        "[7.00s -> 11.00s] the answer depends on the distribution of the hidden variable in this setting",
    ))

    # 8) 相似但不能删：只有模板句相似，核心内容不同
    results.append(run_case(
        "Should not trim - same frame different meaning",
        "[0.00s -> 4.00s] in this example we analyze the training procedure for the first model",
        "[7.00s -> 11.00s] in this example we analyze the convergence behavior of the second model",
    ))

    # 9) 相似但不能删：多行下不同实体
    results.append(run_case(
        "Should not trim - multiline entity changed",
        "[0.00s -> 2.00s] today we review support vector machines\n"
        "[2.00s -> 4.00s] the margin is the key concept",
        "[7.00s -> 9.00s] today we review bayesian networks\n"
        "[9.00s -> 11.00s] the graph structure is the key concept",
    ))

    # 10) 多行完全重复的一部分 + 新增一行
    results.append(run_case(
        "Multiline - exact plus new line",
        "[0.00s -> 2.00s] this is the first point\n"
        "[2.00s -> 4.00s] this is the second point",
        "[7.00s -> 9.00s] this is the second point\n"
        "[9.00s -> 11.00s] this is the third point",
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