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
        article['article']['steps'][0]['number'] = 0
        self.assertTrue(list(validator.iter_errors(article)))
        article['article']['steps'][0]['number'] = 3
        article['article']['steps'][0]['images'] = [{'image_id': 'image-1', 'alt': 'Seal', 'status': 'available'}]
        self.assertEqual(list(validator.iter_errors(article)), [])
        article['article']['steps'][0]['images'][0]['storage_key'] = 'sources/private'
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
        index = spec['paths']['/v1/catalog/vehicles/{vehicle_id}/articles']['get']
        search = next(parameter for parameter in index['parameters'] if parameter.get('name') == 'q')
        self.assertEqual(search['in'], 'query')
        self.assertFalse(search['required'])
        self.assertEqual(search['schema']['maxLength'], 120)
        self.assertIn('grant', search['description'])
        self.assertIn('metadata-only', search['description'])
        article = spec['components']['schemas']['CatalogArticle']
        for field in ('canonical_article_id','source_revision_id','canonical_revision_id',
                      'content_origin','availability','view_revision','review_status','processing'):
            self.assertIn(field, article['properties'])

if __name__ == '__main__':
    unittest.main()
