import json
from pathlib import Path

from eth_utils import to_dict, to_hex, to_tuple
import pytest
from vyper import compiler
from web3 import Web3

from ethpm import Package
from ethpm.tools import builder as b
from pytest_ethereum.deployer import Deployer


@pytest.fixture
def w3():
    w3 = Web3(Web3.EthereumTesterProvider())
    return w3


CONTRACTS_DIR = Path("./contracts")
SOURCES_GLOB = "**/*.vy"


@pytest.fixture
def manifest():
    if not CONTRACTS_DIR.is_dir():
        raise FileNotFoundError("no contracts_dir")
    all_sources = CONTRACTS_DIR.glob(SOURCES_GLOB)
    compiler_output = generate_compiler_output(all_sources)
    composed_contract_types = generate_contract_types(compiler_output)
    composed_inline_sources = generate_inline_sources(compiler_output)
    manifest = b.build(
        {},
        b.package_name("greeter"),
        b.version("1.0.0"),
        b.manifest_version("2"),
        *composed_inline_sources,
        *composed_contract_types,
        b.validate(),
    )
    return manifest


@to_tuple
def generate_inline_sources(compiler_output):
    for path in compiler_output.keys():
        contract_type = path.split("/")[-1].split(".")[0]
        yield b.inline_source(contract_type, compiler_output)


@to_tuple
def generate_contract_types(compiler_output):
    for path in compiler_output.keys():
        contract_type = path.split("/")[-1].split(".")[0]
        yield b.contract_type(contract_type, compiler_output)


@to_dict
def generate_compiler_output(all_sources):
    for source in all_sources:
        contract_file = str(source).split("/")[-1]
        contract_type = contract_file.split(".")[0]
        # todo fix to accomodate multiple types in a single contract file
        yield str(source), {contract_type: create_raw_asset_data(source.read_text())}


def create_raw_asset_data(source: Path):
    return {
        "abi": compiler.mk_full_signature(source),
        "evm": {
            "bytecode": {
                "object": to_hex(compiler.compile(source)),
                "linkReferences": {},
            }
        },
    }


@pytest.fixture
def package(manifest, w3):
    return Package(manifest, w3)


# todo squash deployers
@pytest.fixture
def vy_deployer(package):
    return Deployer(package)


@pytest.fixture
def solc_deployer(w3):
    def _solc_deployer(path):
        manifest = json.loads(path.read_text())
        package = Package(manifest, w3)
        return Deployer(package)

    return _solc_deployer