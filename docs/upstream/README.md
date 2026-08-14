# Upstream register

What we know about the boundary between this fork and upstream, one Markdown file
per item. Entries are added while the reasoning is still fresh, and closed out when
upstream accepts, declines, or independently solves the same problem.

The register holds anything about that boundary **that git cannot derive**. Git
tells you *what* differs between two trees; it cannot tell you why we diverged,
whether the divergence is worth offering upstream, whether upstream has since
solved the same problem another way, or that a file arriving from upstream as a
clean add will silently void a guarantee of ours. Those are the things that get
lost between rebases, so they are what this directory is for.

It started life as an upstreamable-changes list, and outbound candidates are still
the bulk of it - but they are one of three directions (see the index below).

This directory is the source of truth. It replaces the Jira filter
"CLOS Userspace - Elevate artifacts to provide upstream" (filter 21880), which
is retired - a saved filter can only hold ticket keys, and what is actually
needed here is the *technical shape* of the upstream version, which does not fit
in a Jira field.

## Who "upstream" is

Two hops, and the distinction decides where a change can go:

- **AlmaLinux ELevate** (`AlmaLinux/leapp-repository`, branch `almalinux-ng`) is
  our direct upstream. It owns the ELevate-only machinery: `vendors.d` support,
  `repomaputils.py`, the multi-distro key handling.
- **oamg** (`oamg/leapp-repository`) is Red Hat's, upstream of AlmaLinux. It owns
  everything under `repos/system_upgrade/common/` and the version-pair repos.

A change to a `common/` file can go all the way to oamg. A change to
ELevate-only machinery can only go to AlmaLinux, because the code it touches
does not exist at oamg.

## What this directory is not

It is **not an inventory of everything we carry**. Most of our divergence is
CloudLinux-specific by nature and will never go upstream.

It is also **not a rebase conflict map**. Work out the conflict surface when a
rebase actually happens, against the ref you are rebasing onto:

```bash
git diff --name-only "$(git merge-base cloudlinux AlmaLinux/almalinux-ng)" cloudlinux \
  | grep -v '^repos/system_upgrade/cloudlinux/'
```

What this directory gives you at that moment is the short list of places where
**upstream may have implemented the same thing independently**. That is the case
worth checking by hand, because git will not flag it: if upstream now covers the
condition, delete our version instead of resolving a conflict. Two actors
inhibiting on one condition, or a patch that has quietly become dead code, are
both worse than a merge conflict - a conflict at least announces itself. See
`inbound/CLOS-2816-disk-image-size-cap.md` for a case that already happened, and the
`hazard` rows below for ones that have not happened yet.

## Direction of travel

Every entry is one of three, and the direction decides what you do with it:

- **Outbound** - ours, worth offering upstream. The decision is *send a PR, and to
  which upstream*.
- **Inbound** - theirs, arriving on the next rebase. The decision is *drop ours,
  rebuild ours on top, or take theirs*. These are the ones git will not warn you
  about, because a file that is new upstream and absent here arrives as a clean
  add with no conflict.
- **Reference** - mapped, nothing to do. Analysis worth keeping so nobody spends
  the effort twice: upstream defects we deliberately did not patch, fixes that
  turned out to be upstream's own, whole classes that closed.

## Outbound - ours, worth offering upstream

| Change | Upstream target | Status |
|---|---|---|
| [CLOS-3465](outbound/CLOS-3465-netdev-fstab-inhibitor.md) - inhibit on `_netdev` in fstab without `nofail` | oamg `common/actors/checkmountoptions` | candidate |
| [CLOS-4330](outbound/CLOS-4330-networkmanager-unmanaged-devices.md) - inhibit when NetworkManager manages no device | oamg `el8toel9/actors/checkifcfg` | candidate |
| [restore-repository-states](outbound/restore-repository-states.md) - restore repo enabled/disabled state after upgrade | oamg `common/` (new actor + `dnfconfig`) | candidate |
| [CLOS-2565](outbound/CLOS-2565-overlay-shared-mount-points.md) - force shared mount points during overlay creation | oamg `common/libraries/{mounting,overlaygen}.py` | candidate |
| [repomaputils-bom](outbound/repomaputils-bom.md) - strip UTF-8 BOM from `repomaputils.py` | AlmaLinux only | candidate |
| [to-keep-excluded-from-to-upgrade](outbound/to-keep-excluded-from-to-upgrade.md) - should `to_keep` suppress upgrades? | oamg - ask before patching | question |
| [CLOS-4518](outbound/CLOS-4518-cron-to-timer-preset-migration.md) - timers left disabled by a cron-to-timer migration | oamg `common/`, replacing `el8toel9/actors/enablelogrotatetimer` | candidate |
| [CLOS-4518](outbound/CLOS-4518-preset-template-instance-unit-type.md) - preset template instances always expand to `.service` | oamg `common/libraries/systemd.py` | candidate |
| [vendors-and-to-reinstall](outbound/vendors-and-to-reinstall.md) - `vendors.d` handling and `to_reinstall` | AlmaLinux (done) / oamg (`to_reinstall` still offerable) | merged |

## Inbound - theirs, decide at the next rebase

| What arrives | Where from | Do |
|---|---|---|
| [`el8toel9/actors/enablelogrotatetimer`](inbound/enablelogrotatetimer.md) - unconditional `enable_unit('logrotate.timer')` | `AlmaLinux/almalinux-ng-0.24.0` (oamg PR 1501, RHEL-17361) | **hazard** - clean add, no conflict. It overrides the administrator-intent rule in [CLOS-4518](outbound/CLOS-4518-cron-to-timer-preset-migration.md). Delete it on arrival unless ours has been upstreamed by then |
| [`transitionsystemdservicesstates` rewrite](inbound/transitionsystemdservicesstates-oamg-1571.md) - report membership fix | oamg PR 1571 (open, draft) | **hazard** - touches the same library and tests as our `3cf318e2` / `451d923e`. Rebuild ours on top of theirs rather than merging past |
| disk image size cap | oamg | **supersedes-ours** - upstream capped it differently; drop ours ([CLOS-2816](inbound/CLOS-2816-disk-image-size-cap.md)) |
| `dnfconfig` error details | oamg | **supersedes-ours** - upstream did the same thing better 15 months later; take theirs ([dnfconfig-error-details](inbound/dnfconfig-error-details.md)) |

## Reference - mapped, nothing to do

| Item | Why it is here |
|---|---|
| [preset-file-ordering](reference/preset-file-ordering.md) - preset files ordered by path, not filename | upstream defect we deliberately did not patch; the analysis is the artifact |
| [CLOS-2610](reference/CLOS-2610-grub-first-partition-offset.md) - grub first-partition offset | nothing to offer - the fix was upstream's own, cherry-picked here |
| [el7toel8-retired-upstream](reference/el7toel8-retired-upstream.md) | closes a whole class - upstream deleted the el7toel8 repo |

Status values:

**Outbound:**

- `candidate` - judged upstreamable, not offered yet
- `question` - we think upstream has a defect, but the intended semantics are
  unclear; ask before sending a patch
- `submitted` - PR open upstream, link it
- `merged` - upstream carries it; drop ours at the next rebase
- `declined` - upstream said no; we carry it knowingly

**Inbound:**

- `hazard` - arrives without a conflict and changes behaviour we rely on; the row
  says what to do at the rebase
- `supersedes-ours` - upstream solved it another way; drop ours
- `absorbed` - already taken here, nothing left to do

**Reference:**

- `mapped` - analysis only; nothing to send, nothing to drop

`obsolete` was the old name for `supersedes-ours`; entries written before this
directory was renamed from `upstreamable/` may still use it.

## Adding an entry

1. Add a file and an index row, in the same PR that introduces the divergence -
   or, for an inbound or reference item, as soon as you learn it.
   Name it `<TICKET>-<slug>.md`, or just `<slug>.md` when there is no ticket, and
   put it in the subdirectory matching its direction:

   ```
   docs/upstream/
     outbound/    ours, worth offering upstream
     inbound/     theirs, arriving - read this whole folder before a rebase
     reference/   mapped, nothing to do
   ```

   One finding can produce entries in more than one direction: our timer fix is
   outbound, and the upstream actor it collides with is inbound. Give each its own
   file and cross-link them, rather than describing the inbound action inside the
   outbound entry - at a rebase `inbound/` is what gets read, and an instruction
   filed anywhere else will be missed.
2. Add a commit trailer so the set is greppable from history and a missing file
   is detectable. `Upstreamable:` for outbound, `RebaseHazard:` for inbound items
   that need action at the next rebase:

   ```
   Upstreamable: el8toel9/checkifcfg - conf.d unmanaged-devices gap
   RebaseHazard: el8toel9/enablelogrotatetimer - arrives as a clean add, overrides ours
   ```

   ```bash
   git log --grep='^Upstreamable:' --format='%h %s%n    %(trailers:key=Upstreamable,valueonly)'
   git log --grep='^RebaseHazard:' --format='%h %s%n    %(trailers:key=RebaseHazard,valueonly)'
   ```

   `Upstreamable:` is deliberately **not** renamed to match the directory: it is
   already in merged history, and renaming it would orphan every existing query.

   Put the trailer in the message's **last** paragraph, together with any
   `Co-Authored-By:` lines and with no blank line between them. Git parses
   trailers only from the final paragraph, so a blank line above them makes
   `%(trailers:...)` silently expand to nothing while `--grep` still matches -
   the commit looks tagged and is not. The status line below distinguishes the
   two: a commit with a printed value is properly tagged, one with an empty
   value merely mentions the word (this file does, so it self-matches).

Each file should answer four things: what we carry and where, why it is not
CloudLinux-specific, what the change has to look like to be acceptable upstream,
and what evidence establishes that upstream does not already cover it.

## Checking a candidate against upstream

Both upstreams are needed, because their trees have diverged from ours and from
each other:

```bash
git remote add oamg https://github.com/oamg/leapp-repository.git   # once
git fetch oamg main
git fetch AlmaLinux
```

Compare against `oamg/main` and `AlmaLinux/almalinux-ng-<latest>`. Two traps:

- **`oamg/main` has restructured.** It dropped `repos/system_upgrade/el7toel8/`
  entirely and does not carry ELevate-only files such as `repomaputils.py`. A
  bare "path does not exist upstream" therefore does not mean "upstream lacks
  the feature" - check the AlmaLinux ref too, and check whether the path was
  *deleted* rather than never present.
- **A plain `git diff <upstream> cloudlinux -- <file>` mixes both directions.**
  Our base is old, so removed lines are often upstream's later work rather than
  something we deleted. Attribute each hunk with
  `git log -S'<token>' <ref> -- <file>` before concluding it is ours.

## Sweep watermark

A full sweep of the fork's commit log for upstreamable candidates was done on
**2026-07-31**, covering the 294-commit delta from our upstream base
`52f3a153` (2024-08-20) up to `54d7d176`. Every entry in this directory that
predates that date came out of that sweep. A future sweep only needs to look at
commits after `54d7d176`.

The sweep also screened out these, examined at file level and rejected - listed
so nobody spends the effort twice:

- `7d50c287` (checkosrelease extra data), `78ab761c` (combine repomap messages) -
  upstream arrived at equivalent code independently; we were catching up, not
  diverging.
- `11effd99` (grubby `--args` formatting), `01954d66` (XFS ftype=0 disk space
  hint) - both attach to code upstream has since rewritten
  (`format_grubby_args_from_args_set`, the overlay redesign). Nothing left to
  apply them to.
- `bf72d600` (`--allowerasing` on release localinstall) - sits inside a
  CloudLinux-only branch of `userspacegen.py` that has no upstream counterpart.
- `f4959c13` (repofile parser under Python 3.6) - fixes our own `save_repofile`,
  which upstream does not have. It travels with
  `outbound/restore-repository-states.md` or not at all.
- Anything touching `repos/system_upgrade/cloudlinux/`, CLN, cl-MySQL/Governor,
  CageFS, or control-panel detection - CloudLinux-specific by construction. The
  exception is an actor that only *lives* there for packaging reasons while its
  logic is generic; `CLOS-4330` is one, so read before assuming.
