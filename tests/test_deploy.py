"""部署加固器测试"""

from deploy_hardener.dockerizer import Dockerizer
from deploy_hardener.degradation_presets import DegradationPreset
from deploy_hardener.compose_generator import ComposeGenerator
from deploy_hardener.baremetal_generator import BaremetalGenerator


class TestDockerizer:
    """Docker 化测试"""

    def test_generate_dockerfile(self, tmp_path):
        dockerizer = Dockerizer()
        path = dockerizer.generate_dockerfile(str(tmp_path))
        assert "Dockerfile" in path
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "FROM python:3.11-slim" in content
        assert "useradd" in content  # 非 root


class TestDegradationPreset:
    """降级预案测试"""

    def test_default_chain(self):
        preset = DegradationPreset.get_default_chain()
        assert len(preset["chain"]) == 5
        assert preset["thresholds"]["model_error_rate"] == 0.05

    def test_generate_yaml(self, tmp_path):
        path = str(tmp_path / "degradation.yaml")
        DegradationPreset.generate_degradation_yaml(path)
        import os
        assert os.path.exists(path)


class TestComposeGenerator:
    """Compose 生成器测试"""

    def test_generate(self, tmp_path):
        gen = ComposeGenerator()
        path = gen.generate(str(tmp_path))
        import os
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "app" in content
        assert "postgres" in content
        assert "redis" in content


class TestBaremetalGenerator:
    """裸机部署测试"""

    def test_generate(self, tmp_path):
        gen = BaremetalGenerator()
        path = gen.generate(str(tmp_path))
        import os
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "[Service]" in content
        assert "Restart=always" in content