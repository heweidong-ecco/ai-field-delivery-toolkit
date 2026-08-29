原型组装器是工具包的核心模块，提供完整的 Agent 技术栈基础版。所有代码放在 `prototype_assembler/` 目录下，依赖统一底座和已完成的数据准备器。

---

## 一、文件结构总览


```
prototype_assembler/
├── __init__.py
├── harness/
│   ├── __init__.py
│   ├── agent.py              # Agent 主体：生命周期、状态、执行
│   └── state.py              # 状态保存与恢复
├── loops/
│   ├── __init__.py
│   ├── base.py               # Loop 基类
│   ├── react.py              # ReAct 循环
│   └── plan_execute.py       # Plan-and-Execute 循环
├── memory/
│   ├── __init__.py
│   ├── short_term.py         # 短期记忆
│   └── long_term.py          # 长期记忆（基础）
├── tools/
│   ├── __init__.py
│   ├── registry.py           # 工具注册表
│   └── builtin.py            # 内置工具
├── context/
│   ├── __init__.py
│   └── builder.py            # 上下文组装与token预算
├── structured_output/
│   ├── __init__.py
│   └── validator.py          # Schema验证与重试
├── streaming/
│   ├── __init__.py
│   └── sse.py                # SSE流式输出
├── templates/
│   ├── __init__.py
│   ├── qa_agent.py           # 知识问答Agent
│   ├── extract_agent.py      # 信息抽取Agent
│   └── reasoning_agent.py    # 多步推理Agent
└── assembler.py              # 原型组装器入口
```