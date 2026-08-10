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


class TestResolveList:
    """Tests for resolve_list argument building."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = JJCli("/tmp/fake-repo")
        self.captured_args = None

        def capture_run_async(args, callback, **kwargs):
            self.captured_args = args

        self.cli.run_async = capture_run_async

    def test_default_revision(self):
        """Without a revision, no -r flag is passed."""
        self.cli.resolve_list(callback=lambda *args: None)
        assert self.captured_args == ["resolve", "--list"]

    def test_explicit_revision(self):
        """An explicit revision is passed via -r."""
        self.cli.resolve_list(callback=lambda *args: None, revision="abc123")
        assert self.captured_args == ["resolve", "--list", "-r", "abc123"]


class TestGetStatusInfo:
    """Tests for the combined status query."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = JJCli("/tmp/fake-repo")
        self.captured_args = None

        def capture_run_async(args, callback, **kwargs):
            self.captured_args = args

        self.cli.run_async = capture_run_async

    def test_revset_includes_working_copy_and_conflicts(self):
        """The query covers @ and conflicted mutable changes."""
        self.cli.get_status_info(callback=lambda *args: None)
        assert self.captured_args[0] == "log"
        revset = self.captured_args[self.captured_args.index("-r") + 1]
        assert revset == "@ | (mutable() & conflicts())"


class TestOpLog:
    """Tests for op log and op restore argument building."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = JJCli("/tmp/fake-repo")
        self.captured_args = None

        def capture_run_async(args, callback, **kwargs):
            self.captured_args = args

        self.cli.run_async = capture_run_async

    def test_op_log_args(self):
        """op log is queried without graph and with a limit."""
        self.cli.op_log(callback=lambda *args: None, limit=25)
        assert self.captured_args[:5] == ["op", "log", "--no-graph", "-n", "25"]
        assert "-T" in self.captured_args

    def test_op_restore_args(self):
        """op restore is passed the operation id."""
        self.cli.op_restore("abc123def456", callback=lambda *args: None)
        assert self.captured_args == ["op", "restore", "abc123def456"]


class TestAbsorbInteractive:
    """Tests for absorb_interactive argument building."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = JJCli("/tmp/fake-repo")
        self.captured = None

        def capture_editor(diff_content, jj_args, callback):
            self.captured = (diff_content, jj_args)

        self.cli._run_with_diff_editor = capture_editor

    def test_default_source(self):
        """Without a source revision, only absorb --interactive is passed."""
        self.cli.absorb_interactive("some diff", callback=lambda *args: None)
        assert self.captured == ("some diff", ["absorb", "--interactive"])

    def test_explicit_source(self):
        """An explicit source revision is passed via --from."""
        self.cli.absorb_interactive(
            "some diff", callback=lambda *args: None, from_rev="abc123"
        )
        assert self.captured == (
            "some diff",
            ["absorb", "--interactive", "--from", "abc123"],
        )


class TestRestore:
    """Tests for restore argument building."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = JJCli("/tmp/fake-repo")
        self.captured_args = None
        self.captured_editor = None

        def capture_run_async(args, callback, **kwargs):
            self.captured_args = args

        def capture_editor(diff_content, jj_args, callback, reverse=False):
            self.captured_editor = (diff_content, jj_args, reverse)

        self.cli.run_async = capture_run_async
        self.cli._run_with_diff_editor = capture_editor

    def test_restore_paths(self):
        """Paths are passed after a -- separator."""
        self.cli.restore_paths(["a.txt", "src/b.py"], callback=lambda *args: None)
        assert self.captured_args == ["restore", "--", "a.txt", "src/b.py"]

    def test_restore_interactive_reverse_applies(self):
        """Interactive restore reverse-applies the selected diff."""
        self.cli.restore_interactive("some diff", callback=lambda *args: None)
        assert self.captured_editor == (
            "some diff",
            ["restore", "--interactive"],
            True,
        )


class TestNewAndAbandonRevisions:
    """Tests for revision arguments on new and abandon."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = JJCli("/tmp/fake-repo")
        self.captured_args = None

        def capture_run_async(args, callback, **kwargs):
            self.captured_args = args

        self.cli.run_async = capture_run_async

    def test_new_without_revision(self):
        """Default new creates a child of the working copy."""
        self.cli.new(callback=lambda *args: None)
        assert self.captured_args == ["new"]

    def test_new_with_revision_and_message(self):
        """New with a revision creates a child of that revision."""
        self.cli.new(callback=lambda *args: None, message="msg", revision="abc123")
        assert self.captured_args == ["new", "abc123", "-m", "msg"]

    def test_abandon_without_revision(self):
        """Default abandon targets the working copy."""
        self.cli.abandon(callback=lambda *args: None)
        assert self.captured_args == ["abandon"]

    def test_abandon_with_revision(self):
        """Abandon with a revision targets that revision."""
        self.cli.abandon(callback=lambda *args: None, revision="abc123")
        assert self.captured_args == ["abandon", "abc123"]


class TestGetLogGraph:
    """Tests for log graph argument building."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = JJCli("/tmp/fake-repo")
        self.captured_args = None

        def capture_run_async(args, callback, **kwargs):
            self.captured_args = args

        self.cli.run_async = capture_run_async

    def test_default_revset_omits_r_flag(self):
        """Without a revset, jj's configured default is used."""
        self.cli.get_log_graph(callback=lambda *args: None)
        assert self.captured_args[0] == "log"
        assert "-r" not in self.captured_args
        assert "-n" in self.captured_args

    def test_explicit_revset(self):
        """An explicit revset is passed via -r."""
        self.cli.get_log_graph(callback=lambda *args: None, revset="mutable()")
        assert "-r" in self.captured_args
        r_index = self.captured_args.index("-r")
        assert self.captured_args[r_index + 1] == "mutable()"


class TestGetDiffRawPaths:
    """Tests for path restriction on raw diffs."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = JJCli("/tmp/fake-repo")
        self.captured_args = None

        def capture_run_async(args, callback, **kwargs):
            self.captured_args = args

        self.cli.run_async = capture_run_async

    def test_without_paths(self):
        """Without paths, no separator is appended."""
        self.cli.get_diff_raw(callback=lambda *args: None, revision="abc123")
        assert "--" not in self.captured_args
        assert self.captured_args[:3] == ["diff", "-r", "abc123"]

    def test_with_paths(self):
        """Paths are appended after a -- separator."""
        self.cli.get_diff_raw(
            callback=lambda *args: None, revision="abc123", paths=["a.txt"]
        )
        assert self.captured_args[-2:] == ["--", "a.txt"]


class TestFileCommands:
    """Tests for file history, annotate, and evolog argument building."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = JJCli("/tmp/fake-repo")
        self.captured_args = None

        def capture_run_async(args, callback, **kwargs):
            self.captured_args = args

        self.cli.run_async = capture_run_async

    def test_get_log_with_paths(self):
        """Log paths are appended after a -- separator."""
        self.cli.get_log(callback=lambda *args: None, paths=["src/a.py"])
        assert self.captured_args[-2:] == ["--", "src/a.py"]

    def test_get_log_without_paths(self):
        """Without paths, no separator is appended."""
        self.cli.get_log(callback=lambda *args: None)
        assert "--" not in self.captured_args

    def test_evolog_args(self):
        """Evolog is queried for a revision without graph output."""
        self.cli.get_evolog(callback=lambda *args: None, revision="abc123")
        assert self.captured_args[:3] == ["evolog", "-r", "abc123"]
        assert "--no-graph" in self.captured_args

    def test_annotate_args(self):
        """Annotate is passed the file path."""
        self.cli.annotate_file("src/a.py", callback=lambda *args: None)
        assert self.captured_args[:3] == ["file", "annotate", "src/a.py"]
        assert "-T" in self.captured_args


class TestOneLiners:
    """Tests for git push, duplicate, and revert argument building."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = JJCli("/tmp/fake-repo")
        self.captured_args = None

        def capture_run_async(args, callback, **kwargs):
            self.captured_args = args

        self.cli.run_async = capture_run_async

    def test_git_push_args(self):
        """Plain push takes no extra arguments."""
        self.cli.git_push(callback=lambda *args: None)
        assert self.captured_args == ["git", "push"]

    def test_duplicate_default(self):
        """Default duplicate targets the current change."""
        self.cli.duplicate(callback=lambda *args: None)
        assert self.captured_args == ["duplicate"]

    def test_duplicate_with_revision(self):
        """Duplicate with a revision targets that revision."""
        self.cli.duplicate(callback=lambda *args: None, revision="abc123")
        assert self.captured_args == ["duplicate", "abc123"]

    def test_revert_args(self):
        """Revert applies the reverse of a revision on top of @."""
        self.cli.revert("abc123", callback=lambda *args: None)
        assert self.captured_args == ["revert", "-r", "abc123", "--onto", "@"]


class TestTags:
    """Tests for tag argument building."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = JJCli("/tmp/fake-repo")
        self.captured_args = None

        def capture_run_async(args, callback, **kwargs):
            self.captured_args = args

        self.cli.run_async = capture_run_async

    def test_tag_list_args(self):
        """Tag list uses the shared ref template."""
        self.cli.tag_list(callback=lambda *args: None)
        assert self.captured_args[:2] == ["tag", "list"]
        assert "-T" in self.captured_args

    def test_tag_set_args(self):
        """Tag set allows moving existing tags."""
        self.cli.tag_set("v1.0.0", "abc123", callback=lambda *args: None)
        assert self.captured_args == [
            "tag",
            "set",
            "v1.0.0",
            "-r",
            "abc123",
            "--allow-move",
        ]

    def test_tag_delete_args(self):
        """Tag delete passes all names."""
        self.cli.tag_delete(["v1", "v2"], callback=lambda *args: None)
        assert self.captured_args == ["tag", "delete", "v1", "v2"]


class TestFix:
    """Tests for fix argument building."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = JJCli("/tmp/fake-repo")
        self.captured_args = None

        def capture_run_async(args, callback, **kwargs):
            self.captured_args = args

        self.cli.run_async = capture_run_async

    def test_fix_default(self):
        """Default fix uses jj's configured default revset."""
        self.cli.fix(callback=lambda *args: None)
        assert self.captured_args == ["fix"]

    def test_fix_with_source(self):
        """An explicit source is passed via -s."""
        self.cli.fix(callback=lambda *args: None, source="abc123")
        assert self.captured_args == ["fix", "-s", "abc123"]


class TestGitPushAllowConflicts:
    """Tests for the allow-conflicts push flag."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cli = JJCli("/tmp/fake-repo")
        self.captured_args = None

        def capture_run_async(args, callback, **kwargs):
            self.captured_args = args

        self.cli.run_async = capture_run_async

    def test_default_push_omits_flag(self):
        """Default push does not allow conflicts."""
        self.cli.git_push(callback=lambda *args: None)
        assert self.captured_args == ["git", "push"]

    def test_allow_conflicts_flag(self):
        """The flag is appended when requested."""
        self.cli.git_push(callback=lambda *args: None, allow_conflicts=True)
        assert self.captured_args == ["git", "push", "--allow-conflicts"]
