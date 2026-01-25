"""Tests for CLI argument building."""

from core.jj_cli import JJCli


class TestSquashFlexible:
    """Tests for squash_flexible argument building."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = JJCli("/tmp/fake-repo")
        self.captured_args = None

        def capture_run_async(args, callback, **kwargs):
            self.captured_args = args

        self.cli.run_async = capture_run_async

    def test_single_source_builds_from_flag(self):
        """Single source revision uses --from flag."""
        self.cli.squash_flexible(
            sources=["abc123"],
            destination="def456",
            use_dest_message=False,
            callback=lambda *args: None,
        )
        assert self.captured_args == [
            "squash",
            "--from",
            "abc123",
            "--into",
            "def456",
        ]

    def test_multiple_sources_builds_multiple_from_flags(self):
        """Multiple source revisions each get their own --from flag."""
        self.cli.squash_flexible(
            sources=["abc123", "xyz789"],
            destination="def456",
            use_dest_message=False,
            callback=lambda *args: None,
        )
        assert self.captured_args == [
            "squash",
            "--from",
            "abc123",
            "--from",
            "xyz789",
            "--into",
            "def456",
        ]

    def test_destination_builds_into_flag(self):
        """Destination revision uses --into flag."""
        self.cli.squash_flexible(
            sources=["abc123"],
            destination="target",
            use_dest_message=False,
            callback=lambda *args: None,
        )
        assert "--into" in self.captured_args
        into_index = self.captured_args.index("--into")
        assert self.captured_args[into_index + 1] == "target"

    def test_use_dest_message_adds_flag(self):
        """use_dest_message=True adds --use-destination-message flag."""
        self.cli.squash_flexible(
            sources=["abc123"],
            destination="def456",
            use_dest_message=True,
            callback=lambda *args: None,
        )
        assert "--use-destination-message" in self.captured_args


class TestRebaseFlexible:
    """Tests for rebase_flexible argument building."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = JJCli("/tmp/fake-repo")
        self.captured_args = None

        def capture_run_async(args, callback, **kwargs):
            self.captured_args = args

        self.cli.run_async = capture_run_async

    def test_revision_mode_uses_r_flag(self):
        """Source mode 'revision' uses -r flag."""
        self.cli.rebase_flexible(
            source_mode="revision",
            source_rev="abc123",
            dest_mode="onto",
            dest_rev="def456",
            callback=lambda *args: None,
        )
        assert "-r" in self.captured_args
        r_index = self.captured_args.index("-r")
        assert self.captured_args[r_index + 1] == "abc123"

    def test_source_mode_uses_s_flag(self):
        """Source mode 'source' uses -s flag."""
        self.cli.rebase_flexible(
            source_mode="source",
            source_rev="abc123",
            dest_mode="onto",
            dest_rev="def456",
            callback=lambda *args: None,
        )
        assert "-s" in self.captured_args
        s_index = self.captured_args.index("-s")
        assert self.captured_args[s_index + 1] == "abc123"

    def test_branch_mode_uses_b_flag(self):
        """Source mode 'branch' uses -b flag."""
        self.cli.rebase_flexible(
            source_mode="branch",
            source_rev="abc123",
            dest_mode="onto",
            dest_rev="def456",
            callback=lambda *args: None,
        )
        assert "-b" in self.captured_args
        b_index = self.captured_args.index("-b")
        assert self.captured_args[b_index + 1] == "abc123"

    def test_onto_uses_d_flag(self):
        """Destination mode 'onto' uses -d flag."""
        self.cli.rebase_flexible(
            source_mode="revision",
            source_rev="abc123",
            dest_mode="onto",
            dest_rev="def456",
            callback=lambda *args: None,
        )
        assert "-d" in self.captured_args
        d_index = self.captured_args.index("-d")
        assert self.captured_args[d_index + 1] == "def456"

    def test_after_uses_A_flag(self):
        """Destination mode 'after' uses -A flag."""
        self.cli.rebase_flexible(
            source_mode="revision",
            source_rev="abc123",
            dest_mode="after",
            dest_rev="def456",
            callback=lambda *args: None,
        )
        assert "-A" in self.captured_args
        A_index = self.captured_args.index("-A")
        assert self.captured_args[A_index + 1] == "def456"

    def test_before_uses_B_flag(self):
        """Destination mode 'before' uses -B flag."""
        self.cli.rebase_flexible(
            source_mode="revision",
            source_rev="abc123",
            dest_mode="before",
            dest_rev="def456",
            callback=lambda *args: None,
        )
        assert "-B" in self.captured_args
        B_index = self.captured_args.index("-B")
        assert self.captured_args[B_index + 1] == "def456"

    def test_full_rebase_command_structure(self):
        """Verify full rebase command structure."""
        self.cli.rebase_flexible(
            source_mode="source",
            source_rev="feature",
            dest_mode="onto",
            dest_rev="main",
            callback=lambda *args: None,
        )
        assert self.captured_args == ["rebase", "-s", "feature", "-d", "main"]
