from rest_framework import renderers
import json


class CapsuleRenderer(renderers.JSONRenderer):
	"""
	Custom renderer for capsules that formats the response as JSON.
	"""
	charset = 'utf-8'

	def render(self, data, accepted_media_type=None, renderer_context=None):
		if isinstance(data, str):
			return data.encode(self.charset)

		response = json.dumps(data, ensure_ascii=False)
		return response.encode(self.charset) if isinstance(response, str) else response