import hashlib
import hmac
from datetime import timedelta
from enum import Enum
from time import time
from typing import Any, Dict, Optional, cast

from httpx import URL

from hibiapi.api.bika.constants import BikaConstants
from hibiapi.api.bika.net import NetRequest
from hibiapi.utils.cache import cache_config, disable_cache
from hibiapi.utils.net import catch_network_error
from hibiapi.utils.routing import BaseEndpoint, request_headers


class EndpointsType(str, Enum):
    collections = "collections"
    categories = "categories"
    keywords = "keywords"
    advanced_search = "advanced_search"
    category_list = "category_list"
    author_list = "author_list"
    comic_detail = "comic_detail"
    comic_recommendation = "comic_recommendation"
    comic_episodes = "comic_episodes"
    comic_page = "comic_page"
    comic_comments = "comic_comments"
    games = "games"
    game_detail = "game_detail"


class ImageQuality(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    original = "original"


class ResultSort(str, Enum):
    date_descending = "dd"
    date_ascending = "da"
    like_descending = "ld"
    views_descending = "vd"


class BikaEndpoints(BaseEndpoint):
    @staticmethod
    def _sign(url: URL, timestamp_bytes: bytes, nonce: bytes, method: bytes):
        return hmac.new(
            BikaConstants.DIGEST_KEY,
            (
                url.raw_path.lstrip(b"/")
                + timestamp_bytes
                + nonce
                + method
                + BikaConstants.API_KEY
            ).lower(),
            hashlib.sha256,
        ).hexdigest()

    @disable_cache
    @catch_network_error
    async def request(
        self,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        no_token: bool = False,
    ):
        net_client = cast(NetRequest, self.client.net_client)
        if net_client.token is None and not no_token:
            await net_client.login(self)

        headers = {
            "Authorization": net_client.token or "",
            "Time": (current_time := f"{time():.0f}".encode()),
            "Image-Quality": request_headers.get().get(
                "X-Image-Quality", ImageQuality.medium
            ),
            "Nonce": (nonce := hashlib.md5(current_time).hexdigest().encode()),
            "Signature": self._sign(
                request_url := self._join(
                    base=BikaConstants.API_HOST,
                    endpoint=endpoint,
                    params=params or {},
                ),
                current_time,
                nonce,
                b"GET" if body is None else b"POST",
            ),
        }

        response = await (
            self.client.get(request_url, headers=headers)
            if body is None
            else self.client.post(request_url, headers=headers, json=body)
        )
        return response.json()

    @cache_config(ttl=timedelta(days=1))
    async def collections(self):
        return await self.request("collections")

    @cache_config(ttl=timedelta(days=3))
    async def categories(self):
        return await self.request("categories")

    @cache_config(ttl=timedelta(days=3))
    async def keywords(self):
        return await self.request("keywords")

    async def advanced_search(
        self,
        *,
        keyword: str,
        page: int = 1,
        sort: ResultSort = ResultSort.date_descending,
    ):
        return await self.request(
            "comics/advanced-search",
            body={
                "keyword": keyword,
                "page": page,
                "sort": sort,
            },
        )

    async def category_list(
        self,
        *,
        category: str,
        page: int = 1,
        sort: ResultSort = ResultSort.date_descending,
    ):
        return await self.request(
            "comics",
            params={
                "page": page,
                "c": category,
                "s": sort,
            },
        )

    async def author_list(
        self,
        *,
        author: str,
        page: int = 1,
        sort: ResultSort = ResultSort.date_descending,
    ):
        return await self.request(
            "comics",
            params={
                "page": page,
                "a": author,
                "s": sort,
            },
        )

    @cache_config(ttl=timedelta(days=3))
    async def comic_detail(self, *, id: str):
        return await self.request("comics/{id}", params={"id": id})

    async def comic_recommendation(self, *, id: str):
        return await self.request("comics/{id}/recommendation", params={"id": id})

    async def comic_episodes(self, *, id: str, page: int = 1):
        return await self.request(
            "comics/{id}/eps",
            params={
                "id": id,
                "page": page,
            },
        )

    async def comic_page(self, *, id: str, order: int = 1, page: int = 1):
        return await self.request(
            "comics/{id}/order/{order}/pages",
            params={
                "id": id,
                "order": order,
                "page": page,
            },
        )

    async def comic_comments(self, *, id: str, page: int = 1):
        return await self.request(
            "comics/{id}/comments",
            params={
                "id": id,
                "page": page,
            },
        )

    async def games(self, *, page: int = 1):
        return await self.request("games", params={"page": page})

    @cache_config(ttl=timedelta(days=3))
    async def game_detail(self, *, id: str):
        return await self.request("games/{id}", params={"id": id})
