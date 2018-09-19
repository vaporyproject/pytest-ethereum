import cytoolz
from eth_utils import to_canonical_address, to_hex
from eth_utils.toolz import assoc_in, pipe

from ethpm import Package
from pytest_ethereum.exceptions import LinkerError
from pytest_ethereum.utils.linker import (
    create_deployment_data,
    create_latest_block_uri,
    get_deployment_address,
    insert_deployment,
)


def linker(*args):
    return _linker(args)


@cytoolz.curry
def _linker(operations, package):
    return pipe(package, *operations)


def deploy(contract_name, *args):
    """
    Return a newly created package and contract address.
    Will deploy the given contract_name, if data exists in package. If
    a deployment is found on the current w3 instance, it will return that deployment
    rather than creating a new instance.
    """
    return _deploy(contract_name, args)


@cytoolz.curry
def _deploy(contract_name, args, package):
    deployments = package.deployments
    if contract_name in deployments:
        return package, package.deployments[contract_name].address

    # Deploy new instance
    factory = package.get_contract_factory(contract_name)
    tx_hash = factory.constructor(*args).transact()
    tx_receipt = package.w3.eth.waitForTransactionReceipt(tx_hash)
    address = to_canonical_address(tx_receipt.contractAddress)
    # Create manifest copy with new deployment instance
    latest_block_uri = create_latest_block_uri(package.w3, tx_receipt)
    deployment_data = create_deployment_data(contract_name, address, tx_receipt)
    manifest = insert_deployment(
        package, contract_name, deployment_data, latest_block_uri
    )
    return Package(manifest, package.w3), address


@cytoolz.curry
def link(contract, linked_type, package_data):
    """
    Return a new package, created with a new manifest after applying the linked type
    reference to the contract factory.
    """
    package, _ = package_data
    deployment_address = get_deployment_address(linked_type, package)
    unlinked_factory = package.get_contract_factory(contract)
    if not unlinked_factory.needs_bytecode_linking:
        raise LinkerError(
            "Contract factory: {0} does not need bytecode linking, "
            "so it is not a valid contract type for link()".format(
                unlinked_factory.__repr__()
            )
        )
    linked_factory = unlinked_factory.link_bytecode({linked_type: deployment_address})
    # todo replace runtime_bytecode in manifest
    manifest = assoc_in(
        package.package_data,
        ("contract_types", contract, "deployment_bytecode", "bytecode"),
        to_hex(linked_factory.bytecode),
    )
    return Package(manifest, package.w3)