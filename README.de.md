# Echo Dot 2 → EchoLocal → Home Assistant

[English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Español](README.es.md) · [Français](README.fr.md)

Dies ist ein übersetzter Überblick mit Einstiegspfad. Die ausführlichen Anleitungen und Befehle werden derzeit auf Englisch gepflegt und sind unten verlinkt. Die README-Sprache ändert weder Spracherkennung noch Antwortstimme oder Aktivierungswort.

Dieses Projekt beschreibt die Umrüstung eines vorhandenen **Echo Dot der zweiten Generation (RS03QR, BISCUIT)** zu einem Home-Assistant-Sprachsatelliten mit **EchoLocal**. Es enthält Anleitungen, USB-Host-Werkzeuge und nachvollziehbare Schritte zum Trainieren und Prüfen eines Aktivierungsworts. Firmware, Sprachaufnahmen, trainierte Modelle und Zugangsdaten sind nicht enthalten.

![Echo Dot 2 → EchoLocal → Home Assistant](docs/assets/architecture.svg)

## Erste Schritte

1. Prüfen Sie das Modell anhand der [Hardwareübersicht](docs/hardware-compatibility.md) und bestätigen Sie BISCUIT über USB. Ein HA-Eintrag mit dem Namen „Echo“ belegt keine Kompatibilität.
2. Bereiten Sie einen Linux-USB-Host, eine stabile Stromversorgung und ein Datenkabel vor. Der geprüfte Weg nutzt einen Container auf Synology; folgen Sie der [geordneten Anleitung](docs/runbook.md).
3. Führen Sie die [Umrüstung](research/conversion.md) schrittweise durch: Entsperren, TWRP, geprüftes Backup nach dem Entsperren und zueinander passende Fire-OS- und EchoLocal-Versionen. USB dient diesen Arbeiten und der Wiederherstellung.
4. Richten Sie in HA die **ESPHome-Integration** und eine **Assist-Pipeline** mit Spracherkennung, Dialogagent und Sprachausgabe ein. Wählen Sie die Sprache und koppeln Sie das Gerät mit seinem Schlüssel. Prüfen Sie TCP 6053 und die erreichbaren Medienadressen gemäß der [HA-Anleitung](research/ha-integration.md).
5. Prüfen Sie normale Sprache, Antwort, Neustart und Dauerbetrieb mit dem [Abnahmeplan](docs/acceptance-and-batch.md). Nach der Umrüstung arbeitet der Dot über WLAN und seine Stromversorgung; eine dauerhafte USB-Datenverbindung ist nicht nötig.

## Grenzen und Prüfung

Das Ergebnis vom 2. Oktober 2026 beschreibt einen historischen Test mit EchoLocal 0.0.8, nicht den aktuellen Gerätezustand oder die Zuverlässigkeit jeder Version. Die eigenen Aktivierungsphrasen „Привет, Мышка“ und „Привет, котик“ bleiben Experimente: synthetische Messwerte belegen keine zuverlässige Erkennung im Raum. Dot-2-Images dürfen nicht auf Echo, Show oder andere Dot-Generationen übertragen werden. Für die grundlegende Sprachfunktion sind HACS, Music Assistant und ESPHome Device Builder nicht erforderlich. Eine Assist-Pipeline mit Cloud-Diensten benötigt weiterhin Netzwerkzugang.

## Ausführliche Dokumentation

- [Index](docs/README.md)
- [Training und Aufnahmen](training/README.md)
- [Gerätezugriff](docs/device-access.md)
- [Steuerung und Grenzen](docs/device-controls.md)
- [Musik](docs/music-latency.md)
- [Prüfprotokoll](docs/operations-findings.md)
- [Sicherheit](SECURITY.md)
- [Veröffentlichung und Releases](docs/publication.md)
- [Beiträge und Übersetzung](docs/i18n.md)

## Verwandte Projekte

- [EchoMuse / emOS](https://github.com/ha-homelab/ha-echomuse)
- [Echo Show 5 / Android](https://github.com/ha-homelab/ha-echo-show-5)
- [Amazon Echo Home Energy / Alexa](https://github.com/4alvit/amazon-echo-home-voice)

EchoMuse mit emOS ist ein anderer Softwarestack für den Dot. Konfiguration, Zugriff und Wiederherstellung stehen im eigenen Repository. Das Alexa-Projekt behält die ursprüngliche Plattform und macht daraus keinen Assist-Satelliten.
