# Upstreamable changes

Divergences in this fork that we have deliberately judged worth offering to
upstream (AlmaLinux, and through it oamg). One entry per change, added at the
time the change is made, while the reasoning is still fresh.

This file is the source of truth. It replaces the Jira filter
"CLOS Userspace - Elevate artifacts to provide upstream" (filter 21880), which
is retired — a saved filter can only hold ticket keys, and what is actually
needed here is the *technical shape* of the upstream version, which does not fit
in a Jira field.

## What this file is not

It is **not an inventory of everything we carry**. Most of our divergence is
CloudLinux-specific by nature and will never go upstream, and a generated list of
every touched file would be stale within a release.

It is also **not a rebase conflict map**. Work out the conflict surface when a
rebase actually happens, against the upstream ref you are rebasing onto:

```bash
git fetch AlmaLinux
git diff --name-only "$(git merge-base cloudlinux AlmaLinux/almalinux-ng)" cloudlinux \
  | grep -v '^repos/system_upgrade/cloudlinux/'
```

What this file gives you at that moment is the short list of places where
**upstream may have implemented the same thing independently**. That is the case
worth checking by hand, because git will not flag it: if upstream now covers the
condition, delete our version instead of resolving a conflict, and mark the entry
`obsolete` here. Two actors inhibiting on one condition, or a patch that has
quietly become dead code, are both worse than a merge conflict — a conflict at
least announces itself.

## Adding an entry

1. Add a row and a section below, in the same PR that introduces the divergence.
2. Add a commit trailer so the set is greppable from history and a missing row is
   detectable:

   ```
   Upstreamable: el8toel9/checkifcfg — conf.d unmanaged-devices gap
   ```

   ```bash
   git log --grep='^Upstreamable:' --format='%h %s%n    %(trailers:key=Upstreamable,valueonly)'
   ```

Status values: `candidate` (judged upstreamable, not offered yet) ·
`submitted` (PR open upstream, link it) · `merged` (upstream carries it; drop
ours at the next rebase) · `declined` (upstream said no; we carry it knowingly) ·
`obsolete` (upstream solved it another way; drop ours).

| Ticket | Change | Upstream target | Status |
|---|---|---|---|
| CLOS-4330 | Inhibit when NetworkManager is configured to manage no device | `el8toel9/actors/checkifcfg` (extend) | candidate |
| CLOS-2565 | Force creation of shared mount points during overlay creation | `common/libraries/mounting.py`, `common/libraries/overlaygen.py` | candidate |

---

### CLOS-4330 — NetworkManager configured to manage no device

**Ours:** `repos/system_upgrade/cloudlinux/actors/checknetworkmanagerunmanaged/`,
a `ChecksPhase` actor that inhibits when a keyfile under
`/etc/NetworkManager/conf.d` sets `unmanaged-devices=*`.

**Why upstreamable:** the gap is upstream's own. `el8toel9/actors/checkifcfg`
already inhibits on `NM_CONTROLLED=no` in ifcfg files, but never reads
`conf.d`, where the same "do not manage this device" intent can be expressed.
EL9 ships no `network-scripts`, so on RHEL and AlmaLinux the consequence is
identical to ours: nothing brings the interface up after the reboot and the host
is reachable only from the console. Nothing in the check is CloudLinux-specific.

**Upstream form:** fold into `checkifcfg` (or a sibling actor beside it) in
`el8toel9`. Drop the `@run_on_cloudlinux` gate. Drop our explicit
`get_target_major_version()` guard — it exists only because
`repos/system_upgrade/cloudlinux/` loads on every upgrade path, whereas
`el8toel9/` is already scoped. Keep the OpenNebula one-context provenance as an
example, not as the premise.

**Note:** this is upstreamable *because* the design reports rather than mutates.
An earlier revision renamed the offending file during `FinalizationPhase`;
upstream would not accept an actor that silently edits network configuration, and
that version would have been fork-only forever.

### CLOS-2565 — shared mount points during overlay creation

**Ours:** commit `09a1b399`, touching `common/libraries/mounting.py` and
`common/libraries/overlaygen.py`.

**Why upstreamable:** both files are upstream-owned and the change is about
generic overlay/mount propagation during target userspace creation, with no
CloudLinux-specific premise. Carried over from filter 21880.

**Before offering:** confirm it still applies to current upstream —
`overlaygen.py` has changed upstream since, and the fix may have been
superseded there.

## Checked and not upstreamable

Recorded so they are not re-triaged. An entry here means someone established
there is nothing to offer, and why.

### CLOS-2610 — grub `grub_real_boot_time` symbol not found

**Nothing to offer: the fix is upstream's own, cherry-picked here.**

The summary names the boot-time symptom, but the failure was earlier and
different. `update_grub_core` ran `grub2-install /dev/sda` during `RPMUpgrade`
and it refused:

    grub2-install: warning: your core.img is unusually large. It won't fit in
    the embedding area.
    grub2-install: error: will not proceed with blocklists.

The disk's first partition started below 1MiB, leaving too small an MBR gap for
the EL8 `core.img`. `grub2-install` aborted, so the MBR kept the EL7 core while
`/boot/grub2` got EL8 modules — and that mismatch is what produces
`symbol 'grub_real_boot_time' not found` at the next boot.

Upstream already inhibits on the precondition:
`el7toel8/actors/checkfirstpartitionoffset`, authored by mhecko@redhat.com for
[RHEL-3341](https://issues.redhat.com/browse/RHEL-3341) and cherry-picked into
this fork as `982f3b7c` (from upstream `ea6cd791`) on 2024-06-13. The only
subsequent CloudLinux commits touching those files are mechanical rebase
adaptations (`fcacc53b` core-changes update, `a07d42a9` `reporting.Tags` ->
`reporting.Groups`), so there is no CloudLinux delta to send either.

Two things worth knowing from this one:

- The ticket carries the `leapp_provide_to_upstream` label, which is how it
  reached filter 21880. The label was applied at triage, before the fix path was
  known — a label added on intake is a question, not a conclusion.
- Grepping history for `CLOS-2610` finds nothing, because the commit that fixes
  it references the *upstream* ticket. Absence of our key is not evidence that
  nothing was done.

**At rebase time:** once the fork's base includes upstream `ea6cd791`, drop the
cherry-pick rather than resolving a conflict against it.
