# XXX TODO this copies a lot from satellite_upgrade_facts.py, should probably make a fixture
# for fake_package at the least?

from leapp.models import InstalledRPM, RPM, ActiveVendorList, VendorSourceRepos, WpToolkit

RH_PACKAGER = 'Red Hat, Inc. <http://bugzilla.redhat.com/bugzilla>'


def fake_package(pkg_name,version):
    return RPM(name=pkg_name, version=version, release='1.sm01', epoch='1', packager=RH_PACKAGER, arch='noarch',
               pgpsig='RSA/SHA256, Mon 01 Jan 1970 00:00:00 AM -03, Key ID 199e2f91fd431d51')


BOGUS_RPM = fake_package('bogus-bogus', '1.0')
WPTOOLKIT_RPM = fake_package('wp-toolkit-cpanel', '0.1')


def test_no_wptoolkit_vendor_present(current_actor_context):
    current_actor_context.feed(ActiveVendorList(data=list(["jello"])), InstalledRPM(items=[]))
    current_actor_context.run()
    message = current_actor_context.consume(WpToolkit)
    assert not message


def test_no_wptoolkit_rpm_present(current_actor_context):
    current_actor_context.feed(ActiveVendorList(data=list(['wp-toolkit'])), InstalledRPM(items=[]))
    current_actor_context.run()
    message = current_actor_context.consume(WpToolkit)
    assert not hasattr(message, 'variant')
    assert not hasattr(message, 'version')


def test_wptoolkit_rpm_present(current_actor_context):
    current_actor_context.feed(ActiveVendorList(data=list(['wp-toolkit'])), VendorSourceRepos(vendor='wp-toolkit',source_repoids=list(['wp-toolkit-cpanel'])), InstalledRPM(items=[BOGUS_RPM,WPTOOLKIT_RPM]))
    current_actor_context.run()
    message = current_actor_context.consume(WpToolkit)[0]
    assert message.variant == 'cpanel'
    assert message.version == '0.1'
