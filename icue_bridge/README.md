# LedFx → iCUE Bridge

Reçoit les flux UDP de [LedFx](https://www.ledfx.app/) (WLED DRGB/DNRGB/WARLS, DDP ou RGB brut) et les applique aux périphériques Corsair via le SDK iCUE.

## Prérequis

- Windows avec **iCUE** lancé et l'option *SDK* activée (Paramètres iCUE → « Activer le SDK »).
- Python 3.10+ si tu lances depuis les sources : `py -3 -m pip install -r requirements.txt`.
- Le bridge et iCUE doivent tourner avec les mêmes droits (tous deux admin, ou aucun des deux).

## Lancement

Double-clique sur **`lancer_bridge.bat`** : il vérifie Python, installe les dépendances au premier lancement, puis démarre le bridge. Les arguments sont transmis, par exemple `lancer_bridge.bat --mode fusion`.

```
py -3 ledfx_icue_bridge.py              # fenêtre de choix du mode
py -3 ledfx_icue_bridge.py --mode fusion
LedFx_to_ICUE_bridge.exe                # version compilée
```

Au premier lancement de l'exe, un `config.json` par défaut est créé à côté de lui.

### Modes

| Mode | Ports | Description |
|---|---|---|
| `unique` | un port par entrée de `groups` | Un appareil virtuel LedFx par groupe (clavier, RAM, ventilos…). |
| `group` | `group_port` (34983) | Tous les appareils en un seul ruban, dans l'ordre d'énumération iCUE. |
| `fusion` | `fusion_port` (34984) | Un seul ruban ordonné : clavier → tapis → souris → ventilos/AIO → RAM → ventilos AIO. |

Dans LedFx, crée un appareil **WLED** (ou DDP) par port, adresse `127.0.0.1`, avec le nombre de LEDs affiché par `--list-groups`.

### Options en ligne de commande

| Option | Effet |
|---|---|
| `--list-devices` | Liste les appareils iCUE détectés puis quitte. |
| `--list-groups` | Liste les groupes (port, nombre de LEDs) du mode choisi. |
| `--test` / `--test-color R,G,B` | Allume toutes les LEDs (rouge par défaut). |
| `--fan-sweep --fan-index N` | Fait tourner une LED blanche sur le ventilo N (calibrage). |
| `--fan-on 1,2 --fan-color R,G,B` | Allume uniquement certains ventilos. |
| `--debug-udp` | Affiche le débit UDP par groupe chaque seconde. |
| `--debug-icue` | Affiche les erreurs d'écriture iCUE. |
| `--perf-debug [--perf-threshold S]` | Active les traces de latence détaillées. |
| `--config chemin` | Utilise un autre fichier de configuration. |

## Éditeur de disposition

Le bouton **Disposition** de la fenêtre du bridge (actif une fois iCUE connecté) ouvre un éditeur d'ordre des LEDs. Le haut de chaque liste reçoit le début de l'effet LedFx ; on réordonne par glisser-déposer ou avec les flèches.

| Onglet | Ce qu'il règle | Clé écrite |
|---|---|---|
| Ventilateurs | Ordre des ventilateurs du boîtier, mode « une seule surface » et son calibrage, sens dans chaque ventilateur | `fan_group_order`, `fan_surface*`, `fan_led_*`, `fan_direction` |
| AIO | Ordre pompe / ventilateurs du radiateur (le 1er est inséré parmi les ventilateurs en mode fusion) | `aio_cluster_order`, `aio_cluster` |
| Périphériques | Ordre des appareils dans chaque groupe (barrettes de RAM, souris/tapis…) | `device_order` du groupe |
| Mode fusion | Ordre des sections du ruban, position de la pompe | `fusion_order`, `fusion_cpu_after_fan` |

- **Tester le balayage** (onglet Ventilateurs) fait passer une bande blanche sur les ventilateurs dans l'ordre exact où LedFx les parcourra, avec les réglages affichés, même non enregistrés. C'est le moyen de caler le calibrage : iCUE ne fournit pas la position réelle des LEDs d'un Lighting Node Pro ou d'un Commander.
- **Identifier** fait clignoter l'élément sélectionné sur les vraies LEDs pendant 3 s ; les frames LedFx reprennent ensuite.
- L'éditeur part toujours de la configuration actuelle. **Rétablir** revient au dernier état enregistré, et seules les valeurs modifiées sont écrites.
- **Enregistrer et appliquer** écrit `config.json` ; le bridge le recharge tout seul en moins d'une seconde, sans redémarrer. C'est aussi le cas si tu modifies `config.json` à la main (disposition, groupes, ports ; `max_fps`, `brightness`, `gamma` et les réglages de robustesse iCUE demandent un redémarrage).

## Journal

Les logs sont écrits dans `ledfx_icue_bridge.log` à côté du programme (rotation : 1 Mo × 3). C'est le seul retour disponible avec l'exe fenêtré. Les erreurs bloquantes au démarrage s'affichent aussi dans une boîte de dialogue.

## Configuration (`config.json`)

Les clés inconnues (fautes de frappe) sont signalées dans le journal au démarrage, avec une suggestion. Les valeurs numériques invalides sont remplacées par leur défaut, avec un avertissement.

### Général

| Clé | Défaut | Rôle |
|---|---|---|
| `udp_host` | `127.0.0.1` | Interface d'écoute. Mettre `0.0.0.0` si LedFx tourne sur **un autre PC** (tout le réseau local peut alors piloter les LEDs). |
| `protocol` | `drgb` | `drgb`/`wled`/`udp` (WLED, DDP auto-détecté), `ddp`, `raw`, `auto`. |
| `max_fps` | `60` | Débit maximal vers iCUE ; la dernière frame d'une rafale est toujours appliquée. |
| `brightness`, `gamma` | `1.0` | Courbe appliquée à chaque canal. |
| `default_mode`, `startup_prompt` | `unique`, `true` | Mode initial et affichage de la fenêtre de choix. |
| `group_port`, `fusion_port` | `34983`, `34984` | Ports des modes `group` et `fusion`. |
| `fusion_order` | ordre par défaut | Ordre des sections du ruban en mode fusion (voir l'éditeur de disposition). |
| `device_type_mask`, `device_types_include`, `device_types_exclude` | tous | Filtre global des appareils (`CDT_Keyboard`, `CDT_Mouse`, `CDT_Mousemat`, `CDT_MemoryModule`, `CDT_Cooler`, `CDT_LedController`, `CDT_Fan`…). |
| `clear_on_start` | `true` | Éteint les LEDs au démarrage. |
| `process_priority` | `high` | `normal` ou `high` (`realtime` est refusé : risque de gel de Windows). |
| `cpu_affinity_core` | `-1` | `-1` = dernier cœur si ≥ 4 cœurs, `null` = aucune affinité, sinon index du cœur (nécessite `psutil`). |
| `log_level`, `log_file` | `info`, `ledfx_icue_bridge.log` | `log_file: false` désactive le fichier. |
| `ui_language` | auto | `fr` ou `en` ; le bouton *Langue* l'enregistre. |

### Groupes (mode `unique`)

```json
{ "name": "clavier", "udp_port": 6477, "device_types_include": ["CDT_Keyboard"] }
```

Clés possibles : `name`, `udp_port` (obligatoire), `udp_host`, `protocol`, `device_ids`, `device_order` (ordre explicite des appareils, voir l'éditeur), `device_types_include`, `device_types_exclude`, `model_contains`, `serial_contains`, `device_sort` (`x`, `y`, `xy`, `yx`, `model`), `update_mode`, `keepalive_reapply`, `idle_clear_disabled`, `idle_clear_seconds`, `link_mouse_to_mousemat_center`, `ram_group_layout`, `pump_split`.

Un appareil ne peut appartenir qu'à un seul groupe.

### Ordre des LEDs

- **Clavier / RAM / tapis** : `*_serpentine`, `*_serpentine_mode` (`linear` ou `serpentine`), `*_first_dir`, `*_row_order`, `*_rows`, `*_row_tolerance`, `*_flip_x/y`, `*_swap_xy`.
- **Tapis** : `mousemat_order_mode` (`angle`, `index`, `serpentine`), `mousemat_angle_start`, `mousemat_angle_direction`, `mousemat_reverse`.
- **RAM** : `ram_order_axis`, `ram_match_group_order`, `ram_group_layout` (`sticks` ou `rows`), et pour le mode fusion `fusion_ram_mode`, `fusion_ram_mirror`, `fusion_ram_led_axis`.
- **Ventilos en une seule surface** : `fan_surface: true` traite tous les ventilateurs d'un contrôleur comme une seule surface. L'effet LedFx la balaie par tranches, du ventilateur placé en `fan_surface_first` (`top`, `bottom`, `left`, `right`) jusqu'à l'autre bout, dans tous les modes ; en mode fusion, la pompe AIO passe avant (`fusion_cpu_after_fan: 0`) ou après le bloc. Calibrage du câblage : `fan_led_start` (côté de la 1re LED de l'anneau), `fan_led_rotation` (`clockwise`/`counter`), `fan_led_inner_first` (LEDs du centre câblées en premier). `fan_group_order` donne l'ordre physique des ventilateurs.
- **Ventilos** : `fan_ring`, `fan_outer_leds`, `fan_inner_leds`, `fan_count`, `fan_layout` (`sequential`, `cluster`, `auto`), `fan_start`, `fan_direction`, `fan_ring_order`, `fan_group_order`, `fan_group_sort`, `fan_inner_first`, `fan_lock_to_first`, `fan_flip_x/y`, `fan_swap_xy`, `fan_device_types`.
- **AIO** : `aio_cluster`, `aio_cluster_count`, `aio_cluster_sort`, `aio_cluster_order`, `aio_angle_start`, `aio_angle_direction`, `aio_pump_*`, `aio_flip_x/y`, `aio_swap_xy`. `fusion_cpu_after_fan` place la pompe après le N-ième ventilo en mode fusion.
- **Fusion** : `fusion_order` liste les sections dans l'ordre du ruban parmi `clavier`, `tapis`, `souris`, `ventilos`, `ram`, `aio_ventilos` (les sections absentes sont ajoutées à la fin dans l'ordre par défaut).

### Robustesse iCUE

| Clé | Défaut | Rôle |
|---|---|---|
| `icue_update_mode` | `direct_async` | `direct_async` (thread d'écriture dédié), `direct`, `buffer`. |
| `icue_direct_async_timeout`, `icue_restart_on_sdk_hang` | `10`, `true` | Redémarre le processus si un appel iCUE reste bloqué. |
| `icue_apply_fail_threshold` | `6` | Échecs d'écriture consécutifs avant reconnexion. |
| `icue_reconnect_cooldown`, `icue_reconnect_timeout` | `15`, `8` | Délais de reconnexion. |
| `icue_keepalive`, `icue_keepalive_interval`, `icue_keepalive_reapply` | `true`, `5`, `true` | Réapplique la dernière frame quand LedFx est silencieux. |
| `icue_watchdog*` | | Vérification périodique de la session SDK (`icue_watchdog_sdk_check`). |
| `icue_request_control_*` | | Reprise périodique du contrôle des appareils. |
| `icue_layer_priority` | `255` | Priorité de la couche SDK dans iCUE. |
| `unique_idle_clear`, `unique_idle_clear_seconds` | `false`, `1.0` | Éteint un groupe après N secondes sans paquet (mode unique). |

## Développement

```
py -3 -m unittest discover -s tests          # tests (aucun matériel requis)
py -3 -m PyInstaller LedFx_to_ICUE_bridge.spec   # construit dist/LedFx_to_ICUE_bridge.exe
```

`tests/test_runtime.py` exécute la vraie boucle `run_bridge` avec un faux module `cuesdk` et de vrais sockets UDP.
