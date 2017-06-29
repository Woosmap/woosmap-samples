import os
import json
from jsonschema import ValidationError, validate

JSON_TO_VALIDATE = os.path.join(os.getcwd(), 'foodmarkets.json')

WOOSMAP_SCHEMA = {
    '$ref': 'https://raw.githubusercontent.com/woosmap/woosmap-json-schema/master/asset.json#'
}
WOOSMAP_COLLECTION_SCHEMA = {
    '$ref': 'https://raw.githubusercontent.com/woosmap/woosmap-json-schema/master/assetCollection.json#'
}


def load_json(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)


def validate_collection(assets):
    """ Validate an array of Assets expected as {"stores":[{asset},{asset},...]}
        Less time consuming but will raise ValidationError at first error """
    try:
        print("Validating Collection of Assets...")
        validate(assets, WOOSMAP_COLLECTION_SCHEMA)
    except ValidationError as error:
        print Exception("Asset not Matching: {0}".format(error.message))
    else:
        print("...Validated Collection Successful!")


def validate_one_by_one(assets):
    """ Validate individually each Asset that could be useful to identify
        all Asset which could be in wrong schema. A little slower """
    print("Validating assets individually..")
    for item in assets["stores"]:
        try:
            validate(item, WOOSMAP_SCHEMA)
        except ValidationError as error:
            print Exception(
                "Asset not Matching: {0}".format(error.message))
        else:
            print("...Validated Asset {id} Successful!".format(id=item["storeId"]))


def main():
    assets_to_validate = load_json(JSON_TO_VALIDATE)
    validate_collection(assets_to_validate)
    validate_one_by_one(assets_to_validate)


if __name__ == '__main__':
    if os.path.exists(os.path.join(os.getcwd(), JSON_TO_VALIDATE)):
        main()
    else:
        print('File not found: {0} '.format(JSON_TO_VALIDATE))
