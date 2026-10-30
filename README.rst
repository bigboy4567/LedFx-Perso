=====================================================
   Welcome to LedFx ✨ *Making music come alive!*
=====================================================
|Build Status| |License| |Build Status Docs| |Discord|
|Contributor Covenant|

.. image:: https://raw.githubusercontent.com/LedFx/LedFx/main/ledfx_assets/banner.png

Ce fork
-------
Version personnelle de `LedFx <https://github.com/LedFx/LedFx>`_ 2.2.0 (GPL-3.0, comme l'original).
Ajouts par rapport à l'original :

- **Catégorie d'effets « Custom »** (63 effets, ``ledfx/effects/``, aides dans
  ``ledfx/effects/utils/custom.py``) : Section Strobe, Heartbeat, Fireflies, Police Lights,
  Tug of War, Confetti, Kaleidoscope, Color Jump, Interference, Charge Up, Piano Keys,
  Drum Pads, Sound Locator, Lightning, Aurora, Candles, Beat Counter, Neon Sign,
  Vibrating String, Color Organ, Polyrhythm, Phone Paint ; effets de studio et de DJ
  (Sidechain Pump, Trance Gate, Arpeggiator, Wobble, Tape Stop, Phaser, Bitcrush,
  Vinyl Scratch, Riser, Stutter, Swell, Filter Sweep, Chorus, Overdrive, Chopper) ;
  éclairage de scène (Blinders, Stage Wash, Flame Jets, Blacklight, Dance Floor,
  Lens Flare, Lighthouse, Fiber Optic) ; phénomènes lumineux (Doppler, Jacob's Ladder,
  Magma, Freeze, Eclipse, God Rays, Oil Slick, Sandstorm, Wagon Wheel) ; graphisme
  (RGB Split, Palette Cycle, Accordion, Palette Morph, TV Static, Dither, Additive Mix,
  Afterimage, Synthwave Sun).
- **Catégorie « Corsair »** (137 effets) pour le matériel Corsair relié par la passerelle
  LedFx vers iCUE, avec la vraie disposition de chaque LED (``ledfx/effects/utils/corsair_layouts.py``,
  lue dans iCUE) et une disposition de repli pour tout autre ruban :

  - ventilateurs LL sur Lighting Node Pro : Fan Rotor, Fan Meter, Fan Cascade, Fan Vortex,
    Fan Pulse, Fan Pinwheel, Fan Fire, Fan Stack, Fan Planets, Fan Chase, Fan Butterfly,
    Fan Lava, Fan Sparks, Fan Metronome, Fan Spectrum, Fan Relay, Fan Breathe, Fan Strobe,
    Fan Dice, Fan Bounce, Fan Rain, Fan Aurora, Fan Yin Yang, Fan Siren, Fan Starfield,
    Fan Timer, Fan Traffic Light, Fan Storm ;
  - AIO H115i Platinum : Pump Swirl, Pump Gauge, Pump Clock, Pump Radar, Pump Heart,
    Pump Turbine, Pump Thermometer, Pump Eye, Pump Tempo Dial, Pump Boil, Pump Note Wheel,
    Pump Split, Pump Compass, Pump Beat Ring, Pump Orbit, Pump Spectrum, Pump Breathe,
    Pump Beacon, Pump Galaxy, Pump Collide, Pump Mandala, Pump Fireball, Pump Aurora,
    Pump Drip, Pump Strobe, Pump Loop, Pump Sonar (réglage ``top_led`` : la LED de
    l'anneau qui est en haut) ;
  - RAM Vengeance RGB Pro : RAM Meter, RAM Wave, RAM Bar Counter, RAM Fire, RAM Elevators,
    RAM Center Pulse, RAM Mirror Meter, RAM Scanner, RAM Rising, RAM Sparkle, RAM Blocks,
    RAM Plasma, RAM Waterfall, RAM Rain, RAM Breathe, RAM Strobe, RAM Snake, RAM Bounce,
    RAM Lava Lamp, RAM Aurora, RAM Battery, RAM Comets, RAM Pong, RAM Timer, RAM Stairs,
    RAM Glitch, RAM Fireworks ;
  - clavier K95 RGB Platinum : Key Ripple, Key Equalizer, Key Rain, Key Fire, Key Wave,
    Key Spotlight, Key Twinkle, Key Scanner, Key Rows, Key Ghost Typist, Key Plasma, Key Radar,
    Key Warp, Key Snake, Key Fireworks, Key Aurora, Key Spectrogram, Key Breathe, Key Strobe,
    Key Lava Lamp, Key Pong, Key Rainbow, Key Storm, Key Comets, Key Split, Key Spiral,
    Key Checkerboard ;
  - tapis MM800 et souris M55 : Mat Splash, Mat Meter, Mat Chase, Mat Flow, Mat Converge,
    Mat Fire, Mat Sparkle, Mat Split, Mat Halfpipe, Mat Beat Counter, Mouse Pulse, Mat Comets,
    Mat Breathe, Mat Strobe, Mat Rain, Mat Aurora, Mat Spectrum, Mat Lava Lamp, Mat Snake,
    Mat Rainbow, Mat Pulse Line, Mat Ripples, Mat Glitch, Mouse Mood, Mat Timer,
    Mat Fireworks, Mat Siren ;
  - Rig Wave pour les groupes de plusieurs appareils.

- **Pinceau LED** : le téléphone sert de télécommande et peint sur un ruban en le visant
  (gyroscope recalé par la boussole), en l'inclinant (accéléromètre) ou au doigt. Page
  ``/phone``, canal WebSocket ``/api/phone``, effet ``phone_paint``. Les capteurs exigent
  HTTPS : ``tools/phone_cert.py`` crée une autorité locale limitée aux adresses privées et
  au nom du PC, puis le certificat du port sécurisé.
- **Effets cachés** : la catégorie Non-Reactive et quelques autres effets sont retirés du
  sélecteur (``HIDDEN_EFFECTS`` dans ``ledfx/api/schema.py``), sans être supprimés, car
  LedFx s'en sert en interne.
- **Lanceur Windows** ``lancer_ledfx.bat`` : config locale ``dev_config\`` (jamais publiée),
  port 8899, HTTPS du téléphone sur 8900.

What is LedFx?
----------------
LedFx makes your LEDs dance to audio!
What LedFx offers is the ability to take audio input, and instantaneously processes the audio into realtime light show to multiple LED strips/matrix.
No need to spend hours on end to program one song to program your LEDs, as LedFx will do this all for you!

LedFx real-time LED strip music visualization effect controller using is a network based devices (ESP8266/ESP32/Raspberry Pi 4) with support for advanced real-time audio effects! LedFx can control multiple devices and works great with cheap ESP8266/ESP32 nodes allowing for cost effective synchronized effects across your entire house!

Ledfx comes with a browser based front end for configuration, control and live visualisation on port 8888 by default.

| http://localhost:8888
| http://127.0.0.1:8888


Demos
-------

Visit and join our `Discord`_ where community members show off their projects. Check out the #projects or #show-and-tell channels.

📑 Quick start guide and documentation📖
------------------------------------------

Head over to `releases`_ to get the latest releases for Windows and Mac. For linux, use pip.

**Bleeding edge (Experimental)**

If you want the absolute bleeding edge and are not afraid of using the terminal, take a look at the detailed installation instructions here: `Installation documentation`_.

**Documentation**

Documentation for the latest release can be found here: `Stable documentation`_

Documentation built against this repository can be found here: `Latest documentation`_


😍 Show me how to make one!
-----------------------------

The below image describes a basic setup - LedFx running on PC, communicating with a WLED Device controlling an LED strip.

.. image:: https://raw.githubusercontent.com/LedFx/LedFx/main/docs/_static/topology.png

.. list-table::
   :widths: 75 75
   :header-rows: 1

   * - Component
     - Example
   * - Computer running LedFx
     - Windows 10, `LedFx.exe`_
   * - Browser to access the LedFx web interface
     - Chrome/Edge/Firefox/Safari

       http://127.0.0.1:8888
   * - Networked device controlling LED Strip
     - ESP8266 NODEMCU v3 running `WLED`_
   * - Addressable LED strip
     - DC5V WS2812B 5 meters 60LED/m IP67
   * - Power supply for LED Strip and ESP
     - 5V 10 amps LED Power Supply
   * - Something to connect the wires together!
     - Soldering iron/solder

#. **Build your networked LED Strip.**
      - For most, this is the difficult step. Don't worry! There's guides here and online, and plenty of people able to help on WLED and LedFx Discord.
      - Follow the `WLED guide to connect the LED strip and ESP together <https://kno.wled.ge/basics/getting-started/>`_.
      - `Flash WLED to the ESP device <https://kno.wled.ge/basics/install-binary/>`_.
      - Ensure all WLED devices are powered on, and connected to your Wi-Fi.
      - Test you can access the WLED web interface from your PC. If so, then you're good to go!

#. **Install LedFx.**
      - For PC and Mac, see our `releases`_, or see the `installation documentation`_ for more information.
      - For linux, you can use pip to install ledfx - however you may need to install some dependencies first. See the `installation documentation`_ for more information.

#. **Direct computer audio output to LedFx.**
      - By default on Windows LedFx will attempt to listen to your system audio.
      - More information for `Linux and macOS users here <https://ledfx.readthedocs.io/en/latest/settings/directing_audio.html>`_.
      - Play some music in the background.

#. **Start LedFx.**
      - With any desired launch options. See `Command Line Options <https://ledfx.readthedocs.io/en/latest/launch.html>`_.
      - Use --open-ui to open the web interface automatically in your default browser, or navigate to http://127.0.0.1:8888 directly.
      - Your WLED devices should appear in LedFx, automagically configured and ready to go! 🎆🔥
      - If not, on the bottom click Home,  -> ``Scan for WLED devices`` button, or click on the big plus sign and ``Add Device`` to add them manually.
      - If they're still not showing up, make sure they're powered on and properly connected to your WiFi.

#. **Start using effects!**
      - Click on the device, select an effect eg ``scroll`` under Classic
      - Your lights should now be reacting realtime to your music! Enjoy the show 🌈


🧑‍💻 Join the LedFx Community
------------------------------

Join the Discord server to discuss everything about LedFx!  |Discord|

To join, click on the Discord button below:

.. image:: https://discordapp.com/api/guilds/469985374052286474/widget.png?style=banner2
   :width: 30%
   :target: https://discord.com/invite/xyyHEquZKQ

Contributing
--------------
Pull requests are welcome. Once tested, contact LedFx developer community on Discord to discuss the next step.

Please read our `Contributing Guidelines <https://ledfx.readthedocs.io/en/latest/contributing.html>`_ for detailed information on contribution expectations, code quality requirements, and community standards.

We expect and require all contributors to read, understand and follow our `Code of Conduct <https://github.com/LedFx/LedFx/blob/main/CODE_OF_CONDUCT.md>`_.

Credits: `Contributors-&-About`_

License
---------
`GPL-3`_


.. _`GPL-3`: https://choosealicense.com/licenses/gpl-3.0/
.. _`LedFx.exe`: https://github.com/LedFx/LedFx/releases/latest
.. _`LedFx Guide`: https://ledfx.readthedocs.io/en/latest/index.html
.. _`WLED`: https://kno.wled.ge
.. _`releases`: https://github.com/LedFx/LedFx/releases/latest
.. _`Installation documentation`: https://ledfx.readthedocs.io/en/latest/installing.html
.. _`Stable documentation`: https://ledfx.readthedocs.io/en/stable/
.. _`Latest documentation`: https://ledfx.readthedocs.io/en/latest/
.. _`our website`: https://ledfx.app
.. _`Discord`: https://discord.gg/xyyHEquZKQ
.. _`Contributors-&-About`: https://ledfx.app/about/
.. _`How to: Enable Stereo Mix in Windows 10`: https://thegeekpage.com/stereo-mix/


.. |Build Status| image:: https://github.com/LedFx/LedFx/actions/workflows/ci.yml/badge.svg
   :target: https://github.com/LedFx/LedFx/actions/workflows/ci.yml
   :alt: Build Status
.. |Build Status Docs| image:: https://readthedocs.org/projects/ledfx/badge/?version=main
   :target: https://ledfx.readthedocs.io/
   :alt: Documentation Status
.. |License| image:: https://img.shields.io/badge/license-GPL3-blue.svg
   :alt: License
.. |Discord| image:: https://img.shields.io/badge/chat-on%20discord-7289da.svg
   :target: https://discord.gg/xyyHEquZKQ
   :alt: Discord
.. |Contributor Covenant| image:: https://img.shields.io/badge/Contributor%20Covenant-v2.0%20adopted-ff69b4.svg
   :target: CODE_OF_CONDUCT.md
