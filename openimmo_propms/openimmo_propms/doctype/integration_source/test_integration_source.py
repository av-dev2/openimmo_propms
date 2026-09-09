# Copyright (c) 2025, Talib sheikh and Contributors
# See license.txt

# Builds XML only, never parses untrusted input, so there is no XXE surface.
import xml.etree.ElementTree as ET  # nosemgrep
from types import SimpleNamespace

from frappe.tests.utils import FrappeTestCase

from openimmo_propms.services.export_engine import _append_image_attachment, _requires_full_doc


class TestIntegrationSource(FrappeTestCase):
	def test_append_image_attachment_uses_main_child_parent_and_fallback_order(self):
		source = SimpleNamespace(
			image_field="main_picture",
			child_image_field="child_pictures.image",
			parent_image_field="parent_pictures.image",
			fallback_image_field="property_type_symbol",
			image_group="TITELBILD",
			image_location="EXTERN",
			base_media_url="https://example.com",
			target_doctype="Property",
			field_mappings=[],
		)
		record = {
			"main_picture": "/files/main.jpg",
			"child_pictures": [{"image": "/files/child-1.jpg"}, {"image": "/files/child-2.jpg"}],
			"parent_pictures": [{"image": "/files/parent-1.jpg"}],
			"property_type_symbol": "/files/symbol.jpg",
		}
		immobilie = ET.Element("immobilie")

		_append_image_attachment(source, record, immobilie)

		attachments = immobilie.findall("./anhaenge/anhang")
		self.assertEqual(len(attachments), 4)
		self.assertEqual(
			[attachment.findtext("daten") for attachment in attachments],
			[
				"https://example.com/files/main.jpg",
				"https://example.com/files/child-1.jpg",
				"https://example.com/files/child-2.jpg",
				"https://example.com/files/parent-1.jpg",
			],
		)

	def test_append_image_attachment_uses_fallback_when_no_other_images_exist(self):
		source = SimpleNamespace(
			image_field="main_picture",
			child_image_field="child_pictures.image",
			parent_image_field="parent_pictures.image",
			fallback_image_field="property_type_symbol",
			image_group="TITELBILD",
			image_location="EXTERN",
			base_media_url="https://example.com",
			target_doctype="Property",
			field_mappings=[],
		)
		record = {
			"main_picture": None,
			"child_pictures": [],
			"parent_pictures": [],
			"property_type_symbol": "/files/symbol.jpg",
		}
		immobilie = ET.Element("immobilie")

		_append_image_attachment(source, record, immobilie)

		attachments = immobilie.findall("./anhaenge/anhang")
		self.assertEqual(len(attachments), 1)
		self.assertEqual(attachments[0].findtext("daten"), "https://example.com/files/symbol.jpg")

	def test_requires_full_doc_for_dotted_image_fields(self):
		source = SimpleNamespace(
			image_field="main_picture",
			child_image_field="child_pictures.image",
			parent_image_field=None,
			fallback_image_field=None,
			field_mappings=[],
		)

		self.assertTrue(_requires_full_doc(source))
