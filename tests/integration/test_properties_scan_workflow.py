"""Integration tests for the end-to-end ``.properties`` scan workflow."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

from check_unprotected_keys.adapters.reporting import emit_scan_result
from check_unprotected_keys.config.loader import load_search_configuration
from check_unprotected_keys.domain.models import ScanRequest
from check_unprotected_keys.services.scan_service import ScanService

from ..support.fixture_builders import (
    nonempty_output_lines,
    write_pem_private_key,
    write_scan_configuration,
)

_FILENAME_PATTERNS = ("*.properties", "*.key", "*.pem", "id_*")


def _run(root: Path) -> tuple[object, str, str]:
    configuration = load_search_configuration(root)
    result = ScanService().run(
        ScanRequest(execution_root=root, configuration=configuration)
    )
    stdout, stderr = StringIO(), StringIO()
    emit_scan_result(result, stdout=stdout, stderr=stderr)
    return result, stdout.getvalue(), stderr.getvalue()


def test_per_property_findings_and_reference_follow_counts_once(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "keys").mkdir(parents=True)
    write_pem_private_key(project / "keys" / "server.key", encrypted=False)
    props = project / "app.properties"
    props.write_text(
        "spring.datasource.password=hunter2xyz\n"
        "mail.host=${MAIL_HOST}\n"
        "ssl.key.file=keys/server.key\n"
        "audit.password.min.length=8\n",
        encoding="utf-8",
    )
    write_scan_configuration(
        tmp_path, base_folders=("project",), filename_patterns=_FILENAME_PATTERNS
    )

    result, stdout, _stderr = _run(tmp_path)

    props_path = props.resolve()
    key_path = (project / "keys" / "server.key").resolve()
    assert set(nonempty_output_lines(stdout)) == {
        f"{props_path}#spring.datasource.password",
        f"{props_path}#ssl.key.file",
        str(key_path),
    }
    # app.properties + server.key (discovered once; the reference does not re-count it)
    assert result.files_scanned == 2
    assert result.exit_code == 1


def test_referenced_only_key_counts_once(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "secrets").mkdir(parents=True)
    write_pem_private_key(project / "secrets" / "deploy.pem", encrypted=False)
    props = project / "svc.properties"
    props.write_text("service.private.key=secrets/deploy.pem\n", encoding="utf-8")
    # Only *.properties is a candidate pattern, so the key is reached *only* via
    # the reference, not by direct discovery.
    write_scan_configuration(
        tmp_path, base_folders=("project",), filename_patterns=("*.properties",)
    )

    result, stdout, _stderr = _run(tmp_path)

    props_path = props.resolve()
    assert set(nonempty_output_lines(stdout)) == {f"{props_path}#service.private.key"}
    # svc.properties (1) + referenced deploy.pem counted once (1)
    assert result.files_scanned == 2
    assert result.exit_code == 1


def test_benign_properties_file_produces_no_findings(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.properties").write_text(
        "server.port=8080\nspring.profiles.active=prod\n", encoding="utf-8"
    )
    write_scan_configuration(
        tmp_path, base_folders=("project",), filename_patterns=("*.properties",)
    )

    result, stdout, _stderr = _run(tmp_path)

    assert nonempty_output_lines(stdout) == ()
    assert result.files_scanned == 1
    assert result.exit_code == 0


def test_externalized_values_are_not_reported_only_real_secret_is(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.properties").write_text(
        "db.password=${DB_PASSWORD}\n"
        "api.secret=ENC(abc123==)\n"
        "cache.password=\n"
        "audit.password.min.length=8\n"
        "mail.password=R3alSecret99\n",
        encoding="utf-8",
    )
    write_scan_configuration(
        tmp_path, base_folders=("project",), filename_patterns=("*.properties",)
    )

    result, stdout, _stderr = _run(tmp_path)

    props_path = (project / "app.properties").resolve()
    assert set(nonempty_output_lines(stdout)) == {f"{props_path}#mail.password"}
    assert result.exit_code == 1


def test_benign_secret_named_properties_produce_no_findings(tmp_path: Path) -> None:
    # US1 / quickstart Scenario A: every entry is a benign secret-named value.
    project = tmp_path / "project"
    project.mkdir()
    (project / "application.properties").write_text(
        "signing.key.alias=primary\n"
        "jwt.algorithm=RS256\n"
        "cache.key.prefix=user:\n"
        "oauth.token.uri=https://auth.example.com/token\n"
        "password.min.length=8\n"
        "keystore.type=PKCS12\n"
        "key.serializer=org.apache.kafka.common.serialization.StringSerializer\n"
        "db.password=changeme\n"
        "db.host=localhost\n"
        "compass.center=12.5\n",
        encoding="utf-8",
    )
    write_scan_configuration(
        tmp_path, base_folders=("project",), filename_patterns=("*.properties",)
    )

    result, stdout, _stderr = _run(tmp_path)

    assert nonempty_output_lines(stdout) == ()
    assert result.exit_code == 0


def test_secrets_under_benign_key_names_are_reported(tmp_path: Path) -> None:
    # US2 / quickstart Scenario B: signature + literal + inline key material.
    project = tmp_path / "project"
    project.mkdir()
    pem = project / "inline.pem"
    write_pem_private_key(pem, encrypted=False)
    inline = pem.read_text(encoding="utf-8").replace("\n", "\\n")
    pem.unlink()  # keep only the inline copy inside the .properties value
    embedded_secret = "S3cr3tDbPass"
    (project / "app.properties").write_text(
        f"datasource.url=jdbc:mysql://root:{embedded_secret}@db:3306/app\n"
        "mail.password=R3alSecret99\n"
        f"note={inline}\n",
        encoding="utf-8",
    )
    write_scan_configuration(
        tmp_path, base_folders=("project",), filename_patterns=("*.properties",)
    )

    result, stdout, stderr = _run(tmp_path)

    props_path = (project / "app.properties").resolve()
    assert set(nonempty_output_lines(stdout)) == {
        f"{props_path}#datasource.url",
        f"{props_path}#mail.password",
        f"{props_path}#note",
    }
    assert embedded_secret not in stdout
    assert embedded_secret not in stderr
    assert "PRIVATE KEY" not in stdout
    assert result.exit_code == 1


def test_externalized_encrypted_and_certificate_values_are_silent(
    tmp_path: Path,
) -> None:
    # US4 / quickstart Scenario C.
    project = tmp_path / "project"
    project.mkdir()
    (project / "secure.properties").write_text(
        "db.password=${DB_PASSWORD}\n"
        "api.secret=ENC(QkVHRU5jcnlwdA==)\n"
        "jasypt.token={cipher}AAABBBCCCDDD\n"
        "vault.key=vault:secret/data/app#key\n"
        "tpl.password={{ db_password }}\n"
        "tls.cert=-----BEGIN CERTIFICATE-----\\nMIIBex\\n-----END CERTIFICATE-----\n",
        encoding="utf-8",
    )
    write_scan_configuration(
        tmp_path, base_folders=("project",), filename_patterns=("*.properties",)
    )

    result, stdout, _stderr = _run(tmp_path)

    assert nonempty_output_lines(stdout) == ()
    assert result.exit_code == 0


def test_secret_value_never_appears_in_any_output_stream(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    secret_value = "Zx9Qw7Lp2VrTopSecret"
    (project / "app.properties").write_text(
        f"db.password={secret_value}\n", encoding="utf-8"
    )
    write_scan_configuration(
        tmp_path, base_folders=("project",), filename_patterns=("*.properties",)
    )

    result, stdout, stderr = _run(tmp_path)

    props_path = (project / "app.properties").resolve()
    # The path and property key are present; the secret value never is.
    assert f"{props_path}#db.password" in stdout
    assert secret_value not in stdout
    assert secret_value not in stderr
    assert result.exit_code == 1
