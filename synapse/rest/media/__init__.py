# -*- coding: utf-8 -*-
# Copyright 2014-2017 Vector Creations Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from synapse.api.urls import (
    MEDIA_PREFIX, LEGACY_MEDIA_PREFIX,
    CONTENT_REPO_PREFIX,
)
from synapse.rest.media.v0.content_repository import ContentRepoResource
from synapse.rest.media.v1.media_repository import MediaRepositoryResource


def build_media_repo_resource_map(hs, resconfig):
    media_repo = MediaRepositoryResource(hs)
    resource_map = {
        MEDIA_PREFIX: media_repo,
        LEGACY_MEDIA_PREFIX: media_repo,
        CONTENT_REPO_PREFIX: ContentRepoResource(
            hs, hs.config.uploads_path
        ),
    }
    return resource_map
