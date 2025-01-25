#!/usr/bin/python

# Copyright: (c) 2024, Rafael Arrais
# GNU General Public License v3.0+

from __future__ import (absolute_import, division, print_function)

from ansible.module_utils.urls import Request
import json
import urllib.error

__metaclass__ = type

DOCUMENTATION = r'''
---
module: repository

short_description: Module for managing repositories in BorgWarehouse.

# If this is part of a collection, you need to use semantic versioning,
# i.e. the version is of the form "2.5.0" and not "2.4".
version_added: "1.0.2"

description: Module for managing repositories in BorgWarehouse.

options:
    url:
        description: BorgWarehouse URL in the format http://<fqdn>:(<port>).
        required: true
        type: str
    api_token:
        description: BorgBase API_TOKEN.
        required: true
        type: str
    alias:
        description: Repository name.
        required: true
        type: str     
    ssh_public_key:
        description: Repository SSH publick key.
        required: true
        type: str
    state:
        description: Repository state.
        required: false
        type: str
        default: present
        choices: [ absent, present ]
    storageSize:
        description: Repository storage size in GB.
        required: false
        type: int
        default: 10
    alert:
        description: Repository backup alert in seconds.
        required: false
        type: int
        default: 172800
    comment:
        description: Repository backup alert in seconds.
        required: false
        type: str
        default: Managed by Ansible.

author:
    - Rafael Arrais (@rarrais)
'''

EXAMPLES = r'''
- name: Configure repository in BorgWarehouse.
  rarrais.borgwarehouse.repository:
    url: http://borgwarehouse.lan:3000
    api_token: yet-another-secret
    alias: ansibletest
    ssh_public_key: "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIK0wmN/Cr3JXqmLW7u+g9pTh+wyqDHpSQEIQczXkVx9q ansibletest"
'''

RETURN = r'''
repository:
    description: Repository dictionary.
    type: dict
    returned: always
    sample: {
            "alert": 172800,
            "alias": "ansibletest",
            "comment": "Managed by Ansible.",
            "displayDetails": true,
            "id": 1,
            "lanCommand": false,
            "lastSave": 0,
            "repositoryName": "e58c6bdf",
            "sshPublicKey": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIK0wmN/Cr3JXqmLW7u+g9pTh+wyqDHpSQEIQczXkVx9q ansibletest",
            "status": false,
            "storageSize": 10,
            "storageUsed": 0
        }
'''

from ansible.module_utils.basic import AnsibleModule

class BorgWarehouseClient:
    def __init__(self, url, api_token, alias, ssh_public_key, size, alert, comment):
        self.url = url
        self.alias = alias

        self.headers = {
            'Authorization': str('Bearer ' + api_token),
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

        self.data = {
            'alias': alias,
            'sshPublicKey': ssh_public_key,
            'storageSize': size,
            'alert': alert,
            'comment': comment,
            'appendOnlyMode': False,
            'lanCommand': False
        }

        self.session = Request()
        self.repository = self.get_repository()

        if self.repository is not None:
            self.exists = True
            self.id = self.repository['id']
        else:
            self.exists = False

    def get_repository(self):
        get_api_url = self.url + "/api/repo"
        r = self.session.get(get_api_url , headers=self.headers)
        
        repositories = json.loads(r.read())['repoList']

        for repo in repositories:
            if repo['alias'] == self.alias:
                return repo

        return None

    def add_repository(self):     
        add_api_url = self.url + "/api/repo/add"

        self.session.post(add_api_url, data=json.dumps(self.data), headers=self.headers)
        return True

    def edit_repository(self):
        edit_api_url = self.url + "/api/repo/id/" + str(self.id) + "/edit"
        changed = False
        
        if self.repository['sshPublicKey'] != self.data['sshPublicKey']:
            changed = True
        if int(self.repository['storageSize']) != int(self.data['size']):
            changed = True
        if int(self.repository['alert']) != int(self.data['alert']):
            changed = True
        if self.repository['comment'] != self.data['comment']:
            changed = True

        if changed == True:
            self.session.patch(edit_api_url, data=json.dumps(self.data), headers=self.headers)
        
        return changed

    def delete_repo(self):
        delete_api_url = self.url + "/api/repo/id/" + str(self.id) + "/delete"
        data = {'toDelete': True}

        self.session.delete(delete_api_url, data=json.dumps(data), headers=self.headers)
        return True

def run_module():
    module_args = dict(
        url=dict(type='str', required=True),
        api_token=dict(type='str', required=True),
        alias=dict(type='str', required=True),
        ssh_public_key=dict(type='str', required=True),
        state=dict(type='str', required=False, choices=['absent', 'present'], default='present'),
        alert=dict(type='int', required=False, default=172800),
        storageSize=dict(type='int', required=False, default=10),
        comment=dict(type='str', required=False, default="Managed by Ansible.")
    )

    result = dict(
        changed=False,
        repository=""
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    if module.check_mode:
        module.exit_json(**result)

    try:
        changed = False

        repository = BorgWarehouseClient(module.params['url'], 
                                        module.params['api_token'],
                                        module.params['alias'],
                                        module.params['ssh_public_key'],
                                        module.params['storageSize'],
                                        module.params['alert'],
                                        module.params['comment'])


        if not repository.exists and module.params['state'] == 'present':
            changed = repository.add_repository()

        if repository.exists and module.params['state'] == 'present':
            changed = repository.edit_repository()

        if repository.exists and module.params['state'] == 'absent':
            changed = repository.delete_repo()
            pass

        result['repository'] = repository.get_repository()
        result['changed'] = changed

        module.exit_json(**result)

    except urllib.error.HTTPError as e:
        if "500" in str(e):
            module.fail_json(msg="HTTP Error 500: Bad SSH public key", **result)
        if "401" in str(e):
            module.fail_json(msg="HTTP Error 401: Bad API token", **result)
        else:
            module.fail_json(msg=str(e), **result)
    except urllib.error.URLError as e:
        module.fail_json(msg="URL Error: Bad URL", **result)
    except Exception as e:
        module.fail_json(msg=str(type(e).__name__) + ': ' + str(e), **result)

def main():
    run_module()

if __name__ == '__main__':
    main()