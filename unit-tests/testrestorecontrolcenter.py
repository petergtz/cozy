# Cozy Backup Solution
# Copyright (C) ${year}  ${user}
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as published by
# the Free Software Foundation.
#  
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#    
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import unittest
import cozy.restorecontrolcenter
import cozy.restorebackend

class RestoreBackendMock(object):
    VERSION_PRESENT = cozy.restorebackend.RestoreBackend.VERSION_PRESENT
    VERSION_NONE = cozy.restorebackend.RestoreBackend.VERSION_NONE
    versions = range(1, 11)

    def get_previous_version(self, version):
        if version == self.VERSION_PRESENT:
            return self.versions[-1]
        elif version == self.versions[0]:
            return self.VERSION_NONE
        else:
            return version - 1

    def get_next_version(self, version):
        if version == self.VERSION_PRESENT:
            return self.VERSION_NONE
        else:
            return version + 1

    def close_restore_mode(self):
        pass

    def get_all_versions(self):
        result = self.versions[:]
        result.append(self.VERSION_PRESENT)
        return result

class RestoreClientMock(object):
    def go_to_version(self, version):
        pass

class TestRestoreControlCenter(unittest.TestCase):


    def setUp(self):
        self.control_center = cozy.restorecontrolcenter.RestoreControlCenter(RestoreBackendMock(),
                                                       RestoreClientMock())


    def tearDown(self):
        pass

    def test_go_to_version(self):
        self.control_center.go_to_version(5)
        self.assertEquals(self.control_center.current_version, 5)


    def test_go_to_previous_version_starting_with_present(self):
        self.control_center.go_to_previous_version()
        self.assertEquals(self.control_center.current_version, 10)

    def test_go_to_previous_version_starting_with_5(self):
        self.control_center.go_to_version(5)
        self.control_center.go_to_previous_version()
        self.assertEquals(self.control_center.current_version, 4)

    def test_go_to_previous_version_not_existing(self):
        self.control_center.go_to_version(1)
        self.control_center.go_to_previous_version()
        self.assertEquals(self.control_center.current_version, RestoreBackendMock.VERSION_NONE)


    def test_go_to_next_version_starting_with_present(self):
        self.control_center.go_to_next_version()
        self.assertEquals(self.control_center.current_version, RestoreBackendMock.VERSION_NONE)

    def test_go_to_next_version_starting_with_5(self):
        self.control_center.go_to_version(5)
        self.control_center.go_to_next_version()
        self.assertEquals(self.control_center.current_version, 6)

    def test_get_all_versions(self):
        expected = RestoreBackendMock.versions[:]
        expected.append(RestoreBackendMock.VERSION_PRESENT)
        self.assertEqual(self.control_center.get_all_versions(), expected)


if __name__ == "__main__":
    unittest.main()
