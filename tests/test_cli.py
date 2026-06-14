import unittest

from pbobuilder.cli import build_cli_settings, build_parser, derive_output_from_pack_target, is_cli_invocation


class CliTests(unittest.TestCase):
    def test_detects_cli_invocation(self):
        self.assertTrue(is_cli_invocation(["-pack", "src", "out"]))
        self.assertTrue(is_cli_invocation(["--pack-folder", "src"]))
        self.assertFalse(is_cli_invocation([]))

    def test_derives_output_root_and_pbo_name_from_pbo_path(self):
        output_root, pbo_name = derive_output_from_pack_target(
            r"F:\Steam\steamapps\common\DayZServer\@RaiZoClient_Main\Addons\RZ_Weapons.pbo"
        )

        self.assertEqual(output_root, r"F:\Steam\steamapps\common\DayZServer\@RaiZoClient_Main")
        self.assertEqual(pbo_name, "RZ_Weapons")

    def test_default_cli_build_options_are_disabled(self):
        parser = build_parser()
        args = parser.parse_args(["-pack", r"F:\Mods\RZ_Weapons", r"F:\Out\@Client\Addons\RZ_Weapons.pbo"])
        settings = build_cli_settings(args, saved_settings={})

        self.assertFalse(settings["use_binarize"])
        self.assertFalse(settings["convert_config"])
        self.assertFalse(settings["force_rebuild"])
        self.assertFalse(settings["sign_pbos"])
        self.assertFalse(settings["protect_p3d"])
        self.assertFalse(settings["preflight_before_build"])

    def test_cli_flags_enable_build_options(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "-pack",
                r"F:\Mods\RZ_Weapons",
                r"F:\Out\@Client\Addons\RZ_Weapons.pbo",
                "-binarizeP3D",
                "-cppRvmatToBin",
                "-forceRebuild",
                "-protectP3D",
                "-preflight",
            ]
        )
        settings = build_cli_settings(args, saved_settings={})

        self.assertTrue(settings["use_binarize"])
        self.assertTrue(settings["convert_config"])
        self.assertTrue(settings["force_rebuild"])
        self.assertTrue(settings["protect_p3d"])
        self.assertTrue(settings["preflight_before_build"])

    def test_pack_output_overrides_saved_server_root(self):
        parser = build_parser()
        args = parser.parse_args(["-pack", r"F:\Mods\RZ_Server", r"F:\Out\@Server\Addons\RZ_Server.pbo"])
        settings = build_cli_settings(args, saved_settings={"output_root_server": r"F:\Old\@Server"})

        self.assertEqual(settings["output_root_dir"], r"F:\Out\@Server")
        self.assertEqual(settings["output_server_root_dir"], "")

    def test_sign_flags_enable_pbo_signing(self):
        parser = build_parser()

        for flag in ("-signPBO", "--sign-pbo"):
            with self.subTest(flag=flag):
                args = parser.parse_args(
                    ["-pack", r"F:\Mods\RZ_Weapons", r"F:\Out\@Client\Addons\RZ_Weapons.pbo", flag]
                )
                settings = build_cli_settings(args, saved_settings={})

                self.assertTrue(settings["sign_pbos"])


if __name__ == "__main__":
    unittest.main()
