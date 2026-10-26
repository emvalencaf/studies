# Conta Oracle e VM

Status: ready-for-human
Blocked by: -

Criar a conta Oracle Cloud (cartão só para validação), confirmar a cota Always Free vigente na página oficial e subir a VM: ARM A1 com 1–2 OCPU e 6–12 GB; se der "out of capacity", AMD Micro com swap. Ubuntu, chave SSH, portas 80 e 443 abertas na Security List e no firewall da VM. Sugestão: usar o skill `wizard` para guiar.

Critério: `ssh` entra na VM e as portas 80/443 respondem.
