"""提问要素与失败模式的词表。

只放数据和描述，检测逻辑在 diagnose.py。按真实案例校准时优先改这里，
不要改检测流程。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_INPUT_CHARS = 20_000

STATUS_LABELS = {"found": "有", "weak": "弱", "missing": "缺"}


def _p(*patterns: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)


@dataclass(frozen=True)
class SlotSpec:
    id: str
    label: str
    weight: int
    strong: tuple[re.Pattern[str], ...]
    weak: tuple[re.Pattern[str], ...]
    advice: str
    question: str
    placeholder: str


@dataclass(frozen=True)
class PatternSpec:
    id: str
    label: str
    penalty: int
    advice: str
    followup: str


@dataclass(frozen=True)
class ProblemSpec:
    """复盘模式里“上一轮为什么不满意”的分类。"""

    id: str
    label: str
    description: str
    instruction: str
    questions: tuple[str, ...]


# 七个槽位。权重合计 100；缺失扣满权重，薄弱扣一半。
SLOTS = (
    SlotSpec(
        id="goal",
        label="目标",
        weight=25,
        strong=_p(
            r"我想",
            r"我要",
            r"我希望",
            r"希望你能",
            r"想要",
            r"目的是",
            r"目标是",
            r"用来",
            r"我需要",
            r"求一个",
            r"求推荐",
            r"能否",
            r"可不可以",
            r"怎么才能",
            r"如何让",
            r"i want",
            r"help me",
        ),
        weak=_p(r"帮我", r"请帮我", r"怎么", r"如何", r"为什么", r"是什么", r"能不能"),
        advice="说清最终要拿到什么结果，而不只是描述“有问题”。",
        question="你希望最终得到什么？（结论 / 代码 / 步骤 / 对比表）",
        placeholder="你希望最终得到什么结果",
    ),
    SlotSpec(
        id="context",
        label="背景",
        weight=15,
        strong=_p(
            r"背景",
            r"上下文",
            r"目前",
            r"现在",
            r"我在做",
            r"我的项目",
            r"项目中",
            r"版本是",
            r"环境是",
            r"技术栈",
            r"已经试过",
            r"试过",
            r"试了",
            r"使用了",
            r"文件在",
            r"日志",
            r"截图",
            r"复现步骤",
            r"```",
            r"traceback",
            r"exception",
            r"error\s*:",
            r"\d+\s*行",
            r"\.(?:py|js|ts|tsx|jsx|java|go|rs|cpp|cs|php|rb|sql|json|yaml|yml|toml|md)\b",
        ),
        weak=_p(r"遇到", r"出现", r"问题", r"bug", r"错误", r"报错", r"失败", r"不行", r"没反应", r"崩溃"),
        advice="补上你在做什么、环境/版本、已经试过什么；有报错就贴原文。",
        question="你在做什么？环境/版本是什么？已经试过什么？报错原文是什么？",
        placeholder="在做什么、环境、已尝试的做法、报错原文",
    ),
    SlotSpec(
        id="constraints",
        label="约束",
        weight=10,
        strong=_p(
            r"必须",
            r"不要",
            r"不能",
            r"只能",
            r"不允许",
            r"禁止",
            r"限制",
            r"约束",
            r"预算",
            r"截止",
            r"deadline",
            r"之前完成",
            r"不超过",
            r"最多",
            r"至少",
            r"仅限",
            r"兼容",
            r"离线",
            r"不联网",
            r"字数",
            r"篇幅",
            r"控制在",
            r"每天",
            r"每周",
            r"\d+\s*(?:天|周|个月|年|小时|分钟)",
        ),
        weak=_p(r"要求", r"最好", r"尽量"),
        advice="写明硬约束：版本、不能动的东西、时间/篇幅/预算上限。",
        question="有哪些硬约束？（必须满足 / 绝对不能做 / 版本或篇幅上限）",
        placeholder="必须满足和绝对不能做的事",
    ),
    SlotSpec(
        id="output",
        label="期望输出",
        weight=15,
        strong=_p(
            r"输出",
            r"格式",
            r"字数",
            r"字以内",
            r"详细",
            r"简短",
            r"一段",
            r"三条",
            r"几条",
            r"对比",
            r"总结",
            r"大纲",
            r"模板",
            r"清单",
            r"要点",
            r"邮件",
            r"文案",
            r"(?:给|输出|返回|列出|整理|做成|生成|写).{0,8}(?:表格|列表|步骤|代码|函数|脚本|方案|示例|json|markdown)",
            r"(?:分|按).{0,3}步骤",
        ),
        weak=_p(r"给出", r"告诉", r"说明", r"解释", r"写"),
        advice="指定答案的形状：结论/步骤/代码/表格，多长，用什么语言。",
        question="你希望答案长什么样？（结论 / 步骤 / 代码 / 表格；大概多长）",
        placeholder="答案的形式、长度、语言",
    ),
    SlotSpec(
        id="acceptance",
        label="验收标准",
        weight=15,
        strong=_p(
            r"算通过",
            r"验收",
            r"怎样算",
            r"怎么算",
            r"判断标准",
            r"可验证",
            r"能跑通",
            r"跑通",
            r"测试通过",
            r"符合",
            r"满足",
            r"达到",
            r"及格",
            r"能复现",
            r"可复现",
            r"成功标准",
            r"通过标准",
        ),
        weak=_p(r"正确", r"准确", r"可用", r"能用", r"最好", r"尽量"),
        advice="给出“怎样算对”的判据，否则只能得到看起来合理的答案。",
        question="什么情况下你认定这个问题解决了？给一个可验证的判断。",
        placeholder="怎样算解决、怎样算正确",
    ),
    SlotSpec(
        id="audience",
        label="受众/用途",
        weight=10,
        strong=_p(
            r"面向",
            r"受众",
            r"读者",
            r"用户是",
            r"给.{0,6}看",
            r"给.{0,6}用",
            r"用于",
            r"用途",
            r"场景是",
            r"汇报",
            r"面试",
            r"教学",
            r"演讲",
            r"发布给",
            r"给客户",
            r"给老板",
            r"给领导",
        ),
        weak=_p(r"用户", r"客户", r"老板", r"领导", r"同事", r"团队", r"新手", r"专家"),
        advice="说明答案给谁看、用来做什么决定。",
        question="这个答案给谁看、用来做什么？（自己看 / 汇报 / 上线 / 教学）",
        placeholder="给谁看、用来做什么",
    ),
    SlotSpec(
        id="example",
        label="示例",
        weight=10,
        strong=_p(
            r"例如",
            r"比如",
            r"像这样",
            r"参考",
            r"示例",
            r"样例",
            r"类似",
            r"照这个",
            r"反例",
            r"对比",
            r"如下",
        ),
        weak=_p(r"这种", r"那样"),
        advice="贴一个正例或反例，比形容词更能对齐预期。",
        question="有没有一个参考样例，或者一个“不要这样”的反例？",
        placeholder="参考样例或反例",
    ),
)

SLOT_BY_ID = {slot.id: slot for slot in SLOTS}


# 六个反模式。penalty 直接参与扣分；followup 会进入追问清单。
PATTERN_SPECS = (
    PatternSpec(
        id="multi_question",
        label="多问题混装",
        penalty=8,
        advice="一次只问一个主问题，其余拆成后续轮次。",
        followup="这几个问题里，哪个是主问题？先只回答它。",
    ),
    PatternSpec(
        id="no_material",
        label="只报现象不报材料",
        penalty=8,
        advice="贴报错原文、代码片段或复现步骤，别只描述“不行”。",
        followup="把报错原文和相关代码贴出来（可以脱敏）。",
    ),
    PatternSpec(
        id="unverifiable",
        label="目标无法判定",
        penalty=6,
        advice="把“好一点”换成可验证的标准。",
        followup="“好一点”具体指什么？给一个能判断的标准（例如：响应时间 < 200ms）。",
    ),
    PatternSpec(
        id="vague_verb",
        label="祈使句缺对象",
        penalty=5,
        advice="说明对什么做什么，以及期望的产物。",
        followup="具体要处理哪个对象？希望产出什么？",
    ),
    PatternSpec(
        id="assumed_premise",
        label="隐含前提未验证",
        penalty=5,
        advice="先确认前提是否成立，再问原因。",
        followup="先确认这个前提成立吗？你是如何判断“X 不行”的？",
    ),
    PatternSpec(
        id="no_scope",
        label="范围没有边界",
        penalty=5,
        advice="限定领域、时间、水平和产出，否则只能得到泛泛而谈。",
        followup="限定一下范围：你的基础、时间、目标和产出分别是什么？",
    ),
)

PATTERN_BY_ID = {pattern.id: pattern for pattern in PATTERN_SPECS}


# 复盘模式的问题分类。
PROBLEM_TYPES = (
    ProblemSpec(
        id="too_general",
        label="太泛",
        description="回答太笼统，没有落到我的具体情况",
        instruction="只针对我的具体场景回答，不要给通用建议；每条结论附一个具体例子。",
        questions=(
            "把范围收窄到你的具体场景：对象、数据规模、环境分别是什么？",
            "举一个“这个回答不能用”的具体例子。",
        ),
    ),
    ProblemSpec(
        id="off_topic",
        label="跑题",
        description="回答的不是我问的那件事",
        instruction="先复述我的问题，确认你理解的目标；如果理解不一致，先问我，不要直接回答。",
        questions=("用一句话写出你真正要的那件事，和它答的那件事有什么区别？",),
    ),
    ProblemSpec(
        id="wrong_format",
        label="格式不对",
        description="内容也许对，但形式不能用",
        instruction="严格按我给的格式输出；先给一个最小样例让我确认，再展开。",
        questions=("你要的格式是什么？给一个最小样例（表格/JSON/步骤/段落）。",),
    ),
    ProblemSpec(
        id="unverifiable",
        label="无法验证",
        description="结论听起来合理，但没法判断真假",
        instruction="每条结论标注依据（文档、数据或可运行代码）；无法确认的地方明确写“不确定”。",
        questions=("每条结论你打算怎么验证？需要引用、数据还是可运行代码？",),
    ),
    ProblemSpec(
        id="missing_steps",
        label="缺少步骤",
        description="只给了方向，没有可执行的动作",
        instruction="拆成可执行步骤；每步写清输入、动作和预期结果，标出我需要在哪一步做决定。",
        questions=("你需要哪几步？每步的输入和预期结果是什么？",),
    ),
    ProblemSpec(
        id="other",
        label="其他",
        description="它的回答没有满足我的需求",
        instruction="针对我补充的信息重答；先确认理解，再给结论。",
        questions=("用一句话说清：它的回答哪里没满足你？",),
    ),
)

PROBLEM_BY_ID = {problem.id: problem for problem in PROBLEM_TYPES}
