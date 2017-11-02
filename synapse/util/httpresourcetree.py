# Copyright 2016 OpenMarket Ltd
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

import logging

from twisted.web.resource import Resource

logger = logging.getLogger(__name__)


def create_resource_tree(desired_tree, root_resource):
    """Create the resource tree for this Home Server.

    This in unduly complicated because Twisted does not support putting
    child resources more than 1 level deep at a time.

    Args:
        desired_tree (dict[str, Resource])): Desired mapping from path to
            resource.
        root_resource (Resource): The root resource to add the tree to.
    Returns:
        Resource: ``root_resource``
    """

    # keep track of the resources we've created
    resource_mappings = {
        '': root_resource,
    }

    # we sort the path list, as an easy way to start with the shallowest
    # path.
    for full_path in sorted(desired_tree.keys()):
        # check that parents exist all the way down the tree
        last_resource = root_resource
        path = ''
        for path_seg in full_path.split('/')[1:-1]:
            path = path + '/' + path_seg
            child_resource = resource_mappings.get(path)
            if not child_resource:
                # resource doesn't exist, so make a "dummy resource"
                logger.debug("Creating dummy resource for %s", path)
                child_resource = Resource()
                last_resource.putChild(path_seg, child_resource)
                resource_mappings[path] = child_resource
            last_resource = child_resource

        # ===========================
        # now attach the actual desired resource
        last_path_seg = full_path.split('/')[-1]

        assert path + '/' + last_path_seg == full_path
        if full_path in resource_mappings:
            raise Exception("Duplicate mapping for URL %s", full_path)

        res = desired_tree[full_path]
        logger.info("Attaching %s to path %s", res, full_path)

        last_resource.putChild(last_path_seg, res)
        resource_mappings[full_path] = res

    return root_resource
