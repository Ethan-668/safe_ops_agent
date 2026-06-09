from __future__ import annotations

import re


DANGEROUS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\brm\s+-[^\n]*r[^\n]*f",
        r"\brm\s+.*(/|\*)",
        r"\bchmod\s+777\b",
        r"\bchown\b",
        r"\bmkfs(?:\.\w+)?\b",
        r"\bdd\s+if=",
        r"\bsudo\b",
        r"\bsu\s+-",
        r"\bcurl\b.*\|\s*(?:bash|sh)",
        r"\bwget\b.*(?:\|\s*(?:bash|sh)|&&\s*(?:bash|sh))",
        r"\bshutdown\b",
        r"\breboot\b",
        r"\bsystemctl\s+(?:stop|disable|restart)",
        r"\bkill\s+-9\b",
        r">\s*/etc/",
    ]
]

PROMPT_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"忽略.*(?:规则|限制|安全|指令)",
        r"绕过.*(?:规则|限制|安全|检查)",
        r"不需要遵守",
        r"不要遵守.*(?:规则|限制|安全|指令)",
        r"输出计划后.*(?:执行|运行).*(?:危险|删除|删掉|rm|chmod|curl)",
        r"马上(?:执行|运行).*(?:危险|删除|删掉|rm|chmod|curl)",
        r"直接执行.*(?:不要|不用).*解释",
        r"你现在.*(?:管理员|root)",
        r"允许所有操作",
        r"ignore (?:all )?(?:previous|prior|safety|system)",
        r"bypass (?:the )?(?:safety|policy|rules)",
        r"do not follow",
    ]
]

SENSITIVE_PATHS: tuple[str, ...] = (
    "/",
    "/bin",
    "/boot",
    "/dev",
    "/etc",
    "/home",
    "/lib",
    "/lib64",
    "/proc",
    "/root",
    "/run",
    "/sbin",
    "/sys",
    "/tmp",
    "/usr",
    "/var",
    "/var/log",
)

SENSITIVE_FILE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"/etc/passwd",
        r"/etc/shadow",
        r"/etc/sudoers",
        r"/root(?:/|\b)",
        r"\bid_rsa\b",
        r"\.ssh/",
    ]
]

WRITE_WORDS: tuple[str, ...] = (
    "删除",
    "删掉",
    "删",
    "清理",
    "清空",
    "修改",
    "覆盖",
    "写入",
    "移动",
    "归档",
    "改权限",
    "clean",
    "delete",
    "remove",
    "modify",
    "overwrite",
    "write",
    "archive",
    "chmod",
)
