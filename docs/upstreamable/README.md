# Upstreamable changes

Divergences in this fork that we have deliberately judged worth offering to
upstream, one Markdown file per change. Entries are added at the time the change
is made, while the reasoning is still fresh, and closed out when upstream
accepts, declines, or independently solves the same problem.

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
`CLOS-2816-disk-image-size-cap.md` for a case that already happened.

## Open candidates

| Change | Upstream target | Status |
|---|---|---|
| [CLOS-3465](CLOS-3465-netdev-fstab-inhibitor.md) - inhibit on `_netdev` in fstab without `nofail` | oamg `common/actors/checkmountoptions` | candidate |
| [CLOS-4330](CLOS-4330-networkmanager-unmanaged-devices.md) - inhibit when NetworkManager manages no device | oamg `el8toel9/actors/checkifcfg` | candidate |
| [restore-repository-states](restore-repository-states.md) - restore repo enabled/disabled state after upgrade | oamg `common/` (new actor + `dnfconfig`) | candidate |
| [CLOS-2565](CLOS-2565-overlay-shared-mount-points.md) - force shared mount points during overlay creation | oamg `common/libraries/{mounting,overlaygen}.py` | candidate |
| [repomaputils-bom](repomaputils-bom.md) - strip UTF-8 BOM from `repomaputils.py` | AlmaLinux only | candidate |
| [to-keep-excluded-from-to-upgrade](to-keep-excluded-from-to-upgrade.md) - should `to_keep` suppress upgrades? | oamg - ask before patching | question |

## Closed

| Change | Outcome |
|---|---|
| [vendors-and-to-reinstall](vendors-and-to-reinstall.md) | merged into AlmaLinux (PR #114); `to_reinstall` still offerable to oamg |
| [CLOS-2816](CLOS-2816-disk-image-size-cap.md) | obsolete - upstream capped image size differently; drop ours at rebase |
| [dnfconfig-error-details](dnfconfig-error-details.md) | obsolete - upstream did the same thing better 15 months later; take theirs |
| [CLOS-2610](CLOS-2610-grub-first-partition-offset.md) | nothing to offer - the fix was upstream's own, cherry-picked here |
| [el7toel8-retired-upstream](el7toel8-retired-upstream.md) | closes a whole class - upstream deleted the el7toel8 repo |

Status values:

- `candidate` - judged upstreamable, not offered yet
- `question` - we think upstream has a defect, but the intended semantics are
  unclear; ask before sending a patch
- `submitted` - PR open upstream, link it
- `merged` - upstream carries it; drop ours at the next rebase
- `declined` - upstream said no; we carry it knowingly
- `obsolete` - upstream solved it another way; drop ours

## Adding an entry

1. Add a file and an index row, in the same PR that introduces the divergence.
   Name it `<TICKET>-<slug>.md`, or just `<slug>.md` when there is no ticket.
2. Add a commit trailer so the set is greppable from history and a missing file
   is detectable:

   ```
   Upstreamable: el8toel9/checkifcfg - conf.d unmanaged-devices gap
   ```

   ```bash
   git log --grep='^Upstreamable:' --format='%h %s%n    %(trailers:key=Upstreamable,valueonly)'
   ```

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
  `restore-repository-states.md` or not at all.
- Anything touching `repos/system_upgrade/cloudlinux/`, CLN, cl-MySQL/Governor,
  CageFS, or control-panel detection - CloudLinux-specific by construction. The
  exception is an actor that only *lives* there for packaging reasons while its
  logic is generic; `CLOS-4330` is one, so read before assuming.
