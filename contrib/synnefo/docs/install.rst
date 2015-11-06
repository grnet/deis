Prepare your project dir, install required packages and, optionally, initialize
a virtualenv::

    $ mkdir paas && cd paas
    $ sudo apt-get install python python-virtualenv python-dev
    $ virtualenv .venv && source .venv/bin/activate

Install required python tools::

    $ pip install snfinv kamaki ansible pyfscache markupsafe

Configure .kamakirc::
    
    $ kamaki config set cloud.okeanos.url https://accounts.okeanos.grnet.gr/identity/v2.0
    $ kamaki config set cloud.okeanos.token <YOUR_TOKEN_HERE>
    $ kamaki config set ca_certs /etc/ssl/certs/ca-certificates.crt
    $ kamaki quota list
 
Generate an ssh keypair::

    $ ssh-keygen -b 4096 -f /home/user/.ssh/paas_id_rsa -C admin@paas -o -a 500

The keypair will be used to access all the cluster nodes using SSH. It is 
highly suggested to set a key passphrase to protect your key.

Create an inventory file. The file contains specification of your cluster 
nodes. All nodes should be created using a CoreOS image. Notice that you 
should create at least three master nodes in order for `etcd` cluster to 
work properly::

    clouds: [okeanos]

    # defunct role installs python within `/home/core/bin/`
    group_vars:
        nodes:
        ansible_python_interpreter: /home/core/bin/python


    coreos: &coreos
        vars: &coreos_vars
            ansible_ssh_user: core

        users: ['core']
        image: b9236d02-0904-4d00-8967-3279f0053d18 # the image id of CoreOS
        floating_ips: [auto]


    control: &control
        <<: *coreos
        vars:
            <<: *coreos_vars
            fleet_tags: "controlPlane=true,routerMesh=true"
        groups: ['nodes', 'controlplane', 'dataplane']


    data: &data
        <<: *coreos
        vars:
            <<: *coreos_vars
            fleet_tags: "dataPlane=true"
        groups: ['nodes', 'dataplane']


    ssh_key: &ssh_key '/home/user/.ssh/paas_id_rsa.pub'
    project: &project <PROJECT-UUID>


    control_machine: &control_machine
        <<: *control
        keys: [*ssh_key]
        flavor:
            cpu: 4
            ram: 4096
            disk: 40
            disk_type: drbd


    plain_data_machine: &plain_data_machine
        <<: *data
        keys: [*ssh_key]
        flavor:
            cpu: 4
            ram: 4096
            disk: 40
            disk_type: drbd
        floating_ips: [auto]


    provision:
        networks:
            paas:
            type: MAC_FILTERED
            cidr: 10.12.22.0/24

    machines:
        # MASTER NODES (!IMPORTANT: Create at least three master nodes)
        paas-master-node1:
            <<: *control_machine
            networks:
                paas:
                    ip: 10.12.22.1

        paas-master-node2:
            <<: *control_machine
            networks:
                paas:
                    ip: 10.12.22.2

        paas-master-node3:
            <<: *control_machine
            networks:
                paas:
                    ip: 10.12.22.3

        # DATA NODES
        paas-data-node1:
            <<: *plain_data_machine
            networks:
                paas:
                    ip: 10.12.22.101

        paas-data-node2:
            <<: *plain_data_machine
            networks:
                paas:
                    ip: 10.12.22.102


Use the `snfinv` tool to provision the cluster nodes::

    $ snfinv --provision

Once nodes are created and booted, clone the `GRNET` deis fork. The repo 
contains all required ansible roles used to provision your PaaS platform::

    $ git clone https://github.com/grnet/deis.git

Create an `ansible.cfg` file to include the grnet ansible roles::

    [defaults]
    roles_path=deis/contrib/synnefo/roles

You may optionally include nodes in /etc/hosts::

    $ snfinv --list-hosts | sudo tee -a /etc/hosts

This will allow you to refer to cluster nodes using their inventory name,
e.g.::

    $ ssh core@paas-master-node1

Install required ansible roles::

    $ ansible-galaxy install -r deis/contrib/synnefo/requirements.txt -p deis/contrib/synnefo/roles

Initialize an ssh-agent and add private key::

    $ eval `ssh-agent -s`
    $ ssh-add /home/user/.ssh/paas_id_rsa

Bootstrap nodes. This is required as CoreOS does not include a python
interpreter by default.::

    $ ansible-playbook -i `which snfinv` deis/contrib/synnefo/playbooks/bootstrap.yml

Generate an etcd endpoint, replace `3` with the amount of your initial master
nodes. Notice that for each new cluster a new etd discovery url should be
created::

    $ curl -s -w '\n' https://discovery.etcd.io/new?size=3

If you don't already own an SSL certificate, generate a self signed one with 
the following command::

    $ openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes 
    $ mkdir ssl && mv key.pem cert.pem ssl/

Prepare your conf.yml::

    $ cp deis/contrib/synnefo/conf.yml.example ./conf.yml
    $ vim conf.yml

and set the following settings:

    - deis_domain
      The domain your PaaS service will be availbale from. Notice that ansible 
      roles won't handle DNS configuration which should already been setup 
      before cluster initialization.

    - deis_nodes_domain
      Will be used to setup nodes hostnames.

    - deis_tunnel
      Any of the master nodes IP address.

    - deis_nodes_firewall
      List all the private IP addresses of your cluster nodes. Any additional 
      IP included in the list will have unrestricted network access to the 
      cluster nodes, including access to the etcd server. It is suggested to 
      additionally include the IP address of the network or machine you 
      use to manage the cluster.

    - deis_key
      Path to the private part of your ssh keypair.
    
    - etcd_discovery_url
      The discovery url generated by the curl command stated above.

    - deis_core_password
      Will be used to set the `core` user local password. Do not use 
      plaintext format to set this parameter.

    - deis_ssl_key, deis_ssl_cert
      Path to the ssl key and cert files.

    - deis_astakos_auth_url
      Astakos authentication endpoint.
    
    - deis_astakos_auth_access_groups
      A comma separated list of astakos groups. Only users that are in these
      groups will have access to the PaaS service.

Install deisctl tool:

    $ curl -sSL http://deis.io/deisctl/install.sh | sh -s 1.12.0
    $ sudo mv deisctl /usr/local/bin

Install PaaS platform:

    $ ansible-playbook -i `which snfinv` deis/contrib/synnefo/playbooks/ifalos.yml -e deis_allow_reboot=True -e deis_allow_upgrade=True -e deis_allow_install=True

The above command will handle the following tasks:

    * If needed, upgrade CoreOS to the version required by Deis
    * Install all services required for a successful Deis installation
    * Install Deis tools and services
    * Install Deis Kubernetes services
    * Configure etcd entries based on values stated in `conf.yml` 
    * Set the approriate firewall rules on all cluster nodes to harden the PaaS
      service against several types of attacks.

Finally start the required services by running::

    $ DEISCTL_TUNNEL=<deis-master-node-ip> deisctl start platform
    $ DEISCTL_TUNNEL=<deis-master-node-ip> deisctl start k8s

Once the commands above are finished you should be able to access the PaaS
platform using the `deis` client tool.

    $ deis login https://deis.<deis_domain>/

The above roles will register the configured astakos endpoint as an
authentication backend used to authenticate the PaaS users requests. To login 
to the PaaS cluster as an end-user use the credentials provided from the 
`Api Access` view of the affiliated Synnefo service.

TIP: You may keep track of your configuration using git::

    $ git init .
    $ echo "deis\n.venv\nssl" > .gitignore
    $ git add .
    $ git commit -m "Initial commit"

*beware* that you should keep git repository private as sensivite infomration 
related to your PaaS infrastructure may be included in configuration files.
