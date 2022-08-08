import kopf
import kubernetes.config as k8s_config
import kubernetes.client as k8s_client
import logging

import zlib
import hashlib

# -------------
# Compute hash function
# -------------
def compute_hash(_text, _hash):
   if _hash == "CRC32":
       return hex(zlib.crc32(bytes(_text, encoding='utf-8')) & 0xffffffff)
   if _hash == "MD5":
       return hashlib.md5(bytes(_text, encoding='utf-8')).hexdigest()
   if _hash == "SHA512":
       return hashlib.sha512(bytes(_text, encoding='utf-8')).hexdigest()


text_analyzer_crd = k8s_client.V1CustomResourceDefinition(
    api_version="apiextensions.k8s.io/v1",
    kind="CustomResourceDefinition",
    metadata=k8s_client.V1ObjectMeta(name="textanalyzers.operators.mytest.it", namespace="mytest"),
    spec=k8s_client.V1CustomResourceDefinitionSpec(
        group="operators.mytest.it",
        versions=[k8s_client.V1CustomResourceDefinitionVersion(
            name="v1",
            served=True,
            storage=True,
            schema=k8s_client.V1CustomResourceValidation(
                open_apiv3_schema=k8s_client.V1JSONSchemaProps(
                    type="object",
                    properties={
                        "spec": k8s_client.V1JSONSchemaProps(
                            type="object",
                            properties={
                                "text":  k8s_client.V1JSONSchemaProps(type="string"),
                                "hash":  k8s_client.V1JSONSchemaProps(type="string", enum=["CRC32", "MD5", "SHA512"])
                            }
                        ),
                        "status": k8s_client.V1JSONSchemaProps(
                            type="object",
                            x_kubernetes_preserve_unknown_fields=True
                        )
                    }
                )
            ),
            additional_printer_columns=[k8s_client.V1CustomResourceColumnDefinition(
                name="version",
                type="string",
                json_path=".apiVersion",
                priority=0
            ), k8s_client.V1CustomResourceColumnDefinition(
                name="hash",
                type="string",
                json_path=".spec.hash",
                priority=1
            ), k8s_client.V1CustomResourceColumnDefinition(
                name="text",
                type="string",
                json_path=".spec.text",
                priority=1
            )],
        )],
        scope="Namespaced",
        names=k8s_client.V1CustomResourceDefinitionNames(
            plural="textanalyzers",
            singular="textanalyzer",
            kind="TextAnalyzer",
            short_names=["tan"]
        )
    )
)

# ------------------------
# LOADING
# ------------------------
try:
    logging.info("Trying load kube config")
    k8s_config.load_kube_config()
    logging.info("Done!")
except k8s_config.ConfigException:
    k8s_config.load_incluster_config()

# ------------------------
# CRD Creation
# ------------------------
api_instance = k8s_client.ApiextensionsV1Api()
try:
    logging.info("Trying CRD install")
    api_instance.create_custom_resource_definition(text_analyzer_crd)
    logging.info("CRD Installed")
except k8s_client.rest.ApiException as e:
    if e.status == 409:
        logging.info("CRD already exists")
    else:
        raise e


# ------------------------
# CREATE
# ------------------------
@kopf.on.create('operators.mytest.it', 'v1', 'textanalyzers')
def on_create(spec, name, namespace, logger, **kwargs):
    _text = spec['text']
    _hash = spec['hash']
    _h = compute_hash(_text, _hash)
    logging.info("CREATE - " + _text)
    logging.info("{}: {}".format(_hash, _h))

    body = {
            'apiVersion': 'v1',
            'kind': 'ConfigMap',
            'metadata': {
                'name': name + '-cm'
            },
            'data': {
                'hash': _hash,
                'val': _h
            }
           }

    # Adopting references ConfigMap as child of current Custom Resource
    #   "metadata": {
    #     "name": "test-analyzer-1-cm",
    #     "ownerReferences": [
    #       {
    #         "controller": true,
    #         "blockOwnerDeletion": true,
    #         "apiVersion": "operators.mytest.it/v1",
    #         "kind": "TextAnalyzer",
    #         "name": "test-analyzer-1",
    #         "uid": "..."
    #       }
    logging.info("Adopting ConfigMap")
    kopf.adopt(body)
    logging.info("Done!")

    try:
        logging.info("Creating ConfigMap %s" % (name + '-cm'))
        resp = k8s_client.CoreV1Api().create_namespaced_config_map(
            body=body,
            namespace='mytest'
        )
        logging.info(resp)

    except k8s_client.ApiException as e:
        logging.error("Exception when calling CoreV1Api->create_namespaced_config_map: %s\n" % e)

    return {"hash": _h}

# ------------------------
# UPDATE
# ------------------------
@kopf.on.update('operators.mytest.it', 'v1', 'textanalyzers')
def on_update(spec, name, namespace, logger, **kwargs):
    _text = spec['text']
    _hash = spec['hash']
    _h = compute_hash(_text, _hash)
    logging.info("UPDATE - " + _text)
    logging.info("{}: {}".format(_hash, _h))

    try:
        logging.info("Updating ConfigMap %s" % (name + '-cm'))
        resp = k8s_client.CoreV1Api().patch_namespaced_config_map(
            body={
                'data': {
                    'hash': _hash,
                    'val': _h
                }
            },
            name=name + '-cm',
            namespace='mytest'
        )
        logging.info(resp)

    except k8s_client.ApiException as e:
        logging.error("Exception when calling CoreV1Api->patch_namespaced_config_map: %s\n" % e)

    return {"hash": _h}

# ------------------------
# DELETE
# Freeze caused by handlers
#   - https://kopf.readthedocs.io/en/latest/troubleshooting/#finalizers-blocking-deletion
#     kubectl patch textanalyzers.operators.mytest.it test-analyzer-1 -p '{"metadata": {"finalizers": []}}' --type merge
#   - optional=true
# ------------------------
@kopf.on.delete('operators.mytest.it', 'v1', 'textanalyzers')
def on_delete(spec, name, namespace, logger, **kwargs):
    text = spec['text']
    logging.info("DELETE - " + text)

    # No need for delete_namespaced_config_map because it was adopted by the custom resource
