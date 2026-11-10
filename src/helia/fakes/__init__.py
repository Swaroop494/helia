"""Deterministic contract fakes. Never presented as measurements of target code."""

from contracts.models import ExecResult, LLMResponse, Mutant
from helia.io import digest


class FakeLLM:
    def complete(self, model, prompt, settings):
        n = int(digest(prompt)[:4], 16)
        return LLMResponse(
            text=f"from toy import clamp\n\ndef test_boundary_{n}():\n"
            f"    assert clamp(-{n + 1}, 0, 10) == 0\n",
            input_tokens=100,
            output_tokens=50,
            cost_usd=0,
        )


class FakeExecutor:
    def discover(self, root, index):
        return [
            Mutant(
                id=f"fake-{digest(r.id)[:8]}-{i}",
                file=r.file,
                line=r.line,
                region=r.id,
                operator="fake/Boundary",
                occurrence=i,
            )
            for r in index.regions
            for i in range(10)
        ]

    def run(self, root, generated, mutant=None, tests=None):
        return ExecResult(
            target="original",
            outcome="pass",
            duration_s=0.01,
            contexts={
                "toy.py": {
                    "1": ["tests/test_toy.py::test_middle|run"],
                    **({"2": ["tests/test_toy.py::test_middle|run"]} if generated else {}),
                }
            },
            statements={"toy.py": [1, 2, 3]},
            test_outcomes={f"{name}::test_fake": "passed" for name in generated},
        )

    def evaluate(self, root, generated, mutants, baseline):
        output = []
        for m in mutants:
            fails = int(digest(m.id)[:8], 16) % 10 < 2 + len(generated)
            output.append(
                ExecResult(
                    target="mutant",
                    mutant_id=m.id,
                    outcome="assert_fail" if fails else "pass",
                    duration_s=0.01,
                    failures=[
                        {
                            "nodeid": "tests/test_toy.py::test_middle",
                            "phase": "call",
                            "type": "AssertionError",
                            "message": "boundary mismatch",
                            "assertion": True,
                        }
                    ]
                    if fails
                    else [],
                )
            )
        return output
