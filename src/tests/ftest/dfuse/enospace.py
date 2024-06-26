"""
  (C) Copyright 2020-2023 Intel Corporation.

  SPDX-License-Identifier: BSD-2-Clause-Patent
"""

import errno
import os

from apricot import TestWithServers
from dfuse_utils import get_dfuse, start_dfuse
from host_utils import get_local_host


class DfuseEnospace(TestWithServers):
    """Dfuse ENOSPC File base class.

    :avocado: recursive
    """

    def test_dfuse_enospace(self):
        """Jira ID: DAOS-8264.

        Test Description:
            This test is intended to test dfuse writes under enospace
            conditions
        Use cases:
            Create Pool
            Create Posix container
            Mount dfuse
            Create file
            Write to file until error occurs
            The test should then get a enospace error.
        :avocado: tags=all,daily_regression
        :avocado: tags=vm
        :avocado: tags=daosio,dfuse
        :avocado: tags=DfuseEnospace,test_dfuse_enospace
        """
        dfuse_hosts = get_local_host()

        # Create a pool, container and start dfuse.
        self.log_step('Creating a single pool with a POSIX container')
        pool = self.get_pool(connect=False)
        container = self.get_container(pool)

        self.log_step('Starting dfuse')
        dfuse = get_dfuse(self, dfuse_hosts)
        start_dfuse(self, dfuse, pool, container)

        # create large file and perform write to it so that if goes out of
        # space.
        target_file = os.path.join(dfuse.mount_dir.value, 'file.txt')

        self.log_step('Write to file until an error occurs')
        with open(target_file, 'wb', buffering=0) as fd:

            # Use a write size of 128.  On EL 8 this could be 1MiB, however older kernels
            # use 128k, and using a bigger size here than the kernel can support will lead to
            # the kernel splitting writes, and the size check after ENOSPC failing due to writes
            # having partially succeeded.
            write_size = 1024 * 128
            file_size = 0
            while True:
                stat_pre = os.fstat(fd.fileno())
                self.assertEqual(stat_pre.st_size, file_size, 'file size incorrect after write')
                try:
                    fd.write(bytearray(write_size))
                    file_size += write_size
                except OSError as error:
                    if error.errno != errno.ENOSPC:
                        raise
                    self.log.info('File write returned ENOSPACE')
                    stat_post = os.fstat(fd.fileno())
                    # Check that the failed write didn't change the file size.
                    self.assertEqual(stat_pre.st_size, stat_post.st_size,
                                     'file size changed after enospace')

                    break

        # As the pool is smaller in size there will be no reserved space for metadata
        # so this is expected to fail.
        try:
            os.unlink(target_file)
        except OSError as error:
            if error.errno != errno.ENOSPC:
                raise

        self.log.info('Test passed')
