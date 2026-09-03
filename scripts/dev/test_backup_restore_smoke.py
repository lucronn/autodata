import unittest


from backup_restore_smoke import temporary_database_name


class BackupRestoreSmokeTests(unittest.TestCase):
    def test_temporary_database_name_is_scoped_and_safe(self):
        name = temporary_database_name(12345)

        self.assertEqual(name, "autodata_restore_check_12345")
        self.assertRegex(name, r"^autodata_restore_check_[0-9]+$")


if __name__ == "__main__":
    unittest.main()
