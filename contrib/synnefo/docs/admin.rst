Admin tasks
===========

In order to use the `deisctl` tool you should first declare the
`DEISCTL_TUNNEL` environmental variable::

    $ export DEISCTL_TUNNEL=<deis-master-node>

* Use `deisctl list` to get a list of all the essential platform components 
  along with their status.


Add a data node
---------------

* Include node in `inventory.yml` file
* Provision node::

    $ snfinv --provision

* Include node private IP in firewall exceptions in `conf.yml`

* Update firewall rules

  $ ansible-playbook -i `which snfinv` deis/contrib/synnefo/playbooks/ifalos.yml

* Initialize node

  $ ansible-playbook --limit "paas-data-nodeXX" -i `which snfinv` deis/contrib/synnefo/playbooks/ifalos.yml -e deis_allow_reboot=True -e deis_allow_upgrade=True -e deis_allow_install=True


Remove a data node
------------------

* Stop and destroy node
* Remove all node references from `inventory.yml` and `conf.yml` settings
