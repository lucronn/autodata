"""Validate additive public lifecycle fixtures and reject unsafe combinations."""
import json
from pathlib import Path
import unittest
import jsonschema

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / 'packages/contracts/catalog/v1'

class CatalogLifecycleContract(unittest.TestCase):
    def test_public_fixtures_and_rejections(self):
        schema = json.loads((CATALOG / 'article-lifecycle.schema.json').read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
        fixtures = list((CATALOG / 'fixtures').glob('*.json'))
        self.assertEqual(len(fixtures), 9)
        for path in fixtures:
            with self.subTest(path=path.name):
                errors = list(validator.iter_errors(json.loads(path.read_text())))
                if path.name.startswith('rejected-'):
                    self.assertTrue(errors, path.name)
                else:
                    self.assertEqual(errors, [], str(errors))

    def test_actual_r2_steps_preserve_optional_number_and_images(self):
        schema = json.loads((CATALOG / 'article-lifecycle.schema.json').read_text())
        validator = jsonschema.Draft202012Validator(schema)
        article = json.loads((CATALOG / 'fixtures/canonical-completed.json').read_text())
        article['article']['steps'] = [{'action': 'Take off the pump.', 'instructions': [],
                                       'images': [], 'evidence_ids': ['e1', 'e2']}]
        self.assertEqual(list(validator.iter_errors(article)), [])
        for number in (0, -2):
            article['article']['steps'][0]['number'] = number
            self.assertEqual(list(validator.iter_errors(article)), [])
        article['article']['steps'][0]['number'] = 3
        article['article']['steps'][0]['images'] = [{'image_id': 'image-1', 'alt': 'Seal', 'status': 'available'}]
        self.assertEqual(list(validator.iter_errors(article)), [])
        article['article']['steps'][0]['images'][0]['storage_key'] = 'sources/private'
        self.assertTrue(list(validator.iter_errors(article)))

    def test_authored_list_ordinals_and_nested_content(self):
        schema = json.loads((CATALOG / 'article-lifecycle.schema.json').read_text())
        validator = jsonschema.Draft202012Validator(schema)
        article = json.loads((CATALOG / 'fixtures/canonical-completed.json').read_text())
        picture = {'image_id': 'figure-1', 'alt': 'Seal', 'status': 'available'}
        table = {'type': 'table', 'rows': [[{'text': 'Check alignment', 'blocks': [
            {'type': 'image', **picture},
        ]}]]}
        item = {'text': 'Check the seal.', 'number': 0, 'images': [picture], 'blocks': [table]}
        block = {'type': 'ordered_list', 'start': -2, 'items': ['Take off the pump.', item]}
        article['article']['document']['blocks'] = [block]
        self.assertEqual(list(validator.iter_errors(article)), [])
        for number in (True, '4', 2**31, -2**31 - 1):
            item['number'] = number
            with self.subTest(number=number):
                self.assertTrue(list(validator.iter_errors(article)))
        item['number'] = 0
        table['rows'][0][0]['blocks'][0]['storage_key'] = 'sources/private'
        self.assertTrue(list(validator.iter_errors(article)))

    def test_openapi_catalog_cascade_and_lifecycle(self):
        spec = json.loads((ROOT / 'apps/api-go/openapi.json').read_text())
        for path in ('/v1/catalog/years', '/v1/catalog/years/{year}/makes',
                     '/v1/catalog/years/{year}/makes/{make}/models',
                     '/v1/catalog/years/{year}/makes/{make}/models/{model}/configurations',
                     '/v1/catalog/vehicles/{vehicle_id}/articles',
                     '/v1/catalog/vehicles/{vehicle_id}/articles/{article_id}',
                     '/v1/catalog/vehicles/{vehicle_id}/articles/{article_id}/source',
                     '/v1/catalog/images/{token}'):
            self.assertIn(path, spec['paths'])
        detail = spec['paths']['/v1/catalog/vehicles/{vehicle_id}/articles/{article_id}']['get']
        for status in ('200','202','401','403','404','409','410','422','429','503'):
            self.assertIn(status, detail['responses'])
        article = spec['components']['schemas']['CatalogArticle']
        for field in ('canonical_article_id','source_revision_id','canonical_revision_id',
                      'content_origin','availability','view_revision','review_status','processing'):
            self.assertIn(field, article['properties'])

    def test_catalog_article_link_exposes_only_resolved_canonical_identity(self):
        schema = json.loads((CATALOG / 'article-lifecycle.schema.json').read_text())
        validator = jsonschema.Draft202012Validator(schema)
        article = json.loads((CATALOG / 'fixtures/canonical-completed.json').read_text())
        block = {'type': 'link', 'text': 'Read the related procedure'}
        article['article']['document']['blocks'] = [
            {'type': 'unordered_list', 'items': [{'text': '', 'blocks': [block]}]},
        ]
        self.assertEqual(list(validator.iter_errors(article)), [])
        block['target_article_id'] = '21391c07-417f-4c86-b9a7-d0b2670bb8a4'
        self.assertEqual(list(validator.iter_errors(article)), [])
        for invalid in (
            {'target_article_id': 'https://example.invalid/private'},
            {'target_ref_sha256': 'a' * 64},
            {'type': 'paragraph'},
        ):
            original = block.copy()
            with self.subTest(invalid=invalid):
                block.update(invalid)
                self.assertTrue(list(validator.iter_errors(article)))
            block.clear()
            block.update(original)

if __name__ == '__main__':
    unittest.main()
