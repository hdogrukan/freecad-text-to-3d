import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from freecad_bridge import FreeCADBridge


def make_config(output_dir):
    return SimpleNamespace(
        OUTPUT_DIR=output_dir,
        PLATFORM="Darwin",
        FREECAD_APP_PATH="",
        FREECAD_PATH=os.path.join(output_dir, "FreeCADCmd"),
        FREECAD_GUI=os.path.join(output_dir, "FreeCAD"),
        EVENT_LOG_PATH=os.path.join(output_dir, "events.jsonl"),
    )


class FreeCADBridgeGuiTests(unittest.TestCase):
    def test_successful_run_opens_stable_latest_alias_in_gui(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = make_config(tmpdir)
            bridge = FreeCADBridge(config)
            script_path = os.path.join(tmpdir, "current_model.py")
            model_path = os.path.join(tmpdir, "model_20260505-114248_355.FCStd")
            bridge._latest_model_path = model_path

            for path in (config.FREECAD_PATH, config.FREECAD_GUI, script_path, model_path):
                with open(path, "w", encoding="utf-8") as f:
                    f.write("placeholder")

            result = SimpleNamespace(
                returncode=0,
                stdout=f"MODEL_OK:{model_path}\n",
                stderr="",
            )

            with patch("freecad_bridge.subprocess.run", return_value=result), \
                 patch.object(bridge, "_inspect_model_file", return_value={"object_count": 1, "techdraw_pages": []}), \
                 patch.object(bridge, "_open_model_in_gui", return_value=(True, "ok")) as open_model:
                success, message = bridge._execute_via_freecadcmd(script_path)

            self.assertTrue(success)
            self.assertEqual(message, "Model updated and opened in FreeCAD")
            open_model.assert_called_once_with(os.path.join(tmpdir, "latest.FCStd"))

    def test_generated_gui_bridge_closes_previous_app_documents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config = make_config(tmpdir)
            bridge = FreeCADBridge(config)

            with open(config.FREECAD_GUI, "w", encoding="utf-8") as f:
                f.write("placeholder")

            with patch("freecad_bridge.subprocess.Popen", return_value=Mock()):
                bridge._launch_gui_bridge(os.path.join(tmpdir, "latest.FCStd"))

            with open(os.path.join(tmpdir, "open_latest_in_gui.py"), "r", encoding="utf-8") as f:
                script = f.read()

            compile(script, "open_latest_in_gui.py", "exec")
            self.assertIn("def read_state():", script)
            self.assertIn("def close_app_generated_documents(except_name=None):", script)
            self.assertIn('basename == "latest.FCStd" or basename.startswith("model_")', script)
            self.assertIn("previously_closed = close_app_generated_documents()", script)
            self.assertIn("additionally_closed = close_app_generated_documents(except_name=doc.Name)", script)
            self.assertIn("closed_documents=closed_documents", script)


if __name__ == "__main__":
    unittest.main()
