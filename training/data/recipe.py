"""Pinned synthesis profiles; the original pm-v1 vocabulary remains unchanged."""

REVISION = 'c10ece1aade47bb51c153c893d14e5bf8e5b7117'

REPO = 'rhasspy/piper-voices'

MASTER_SEED = 20261001

VOICES = ('dmitri', 'denis', 'irina', 'ruslan')

POSITIVES = ('Привет, Мышка.', 'Привет Мышка!', 'Привет, Мышка?', 'Привет Мышка', 'Привет, мышка!', 'Привет, Мышка')

NEGATIVES = ('Привет, Миша.',
 'Привет, Мишка.',
 'Привет, Машка.',
 'Привет, Маша.',
 'Привет, малышка.',
 'Привет, мышь.',
 'Привет, Мишенька.',
 'Привет, Маришка.',
 'Привет, Димка.',
 'Привет, Мила.',
 'Мышка.',
 'Миша.',
 'Мишка.',
 'Мышь.',
 'Привет.',
 'Мышки.',
 'Мышку.',
 'Книжка.',
 'Малышка.',
 'Где моя мышка?',
 'Мышка не работает.',
 'Дай мне мышку.',
 'Я видел мышку.',
 'Купи новую мышку.',
 'Мышка лежит на столе.',
 'Мишка спит.',
 'Миша, иди сюда.',
 'Передай привет Мише.',
 'Передай привет Маше.',
 'Приведи Мишку.',
 'Привет, как дела?',
 'Привет всем.',
 'Всем привет.',
 'Большой привет.',
 'Добрый день.',
 'Доброе утро.',
 'Добрый вечер.',
 'До свидания.',
 'Включи свет.',
 'Выключи свет.',
 'Поставь таймер на пять минут.',
 'Сколько сейчас времени?',
 'Какая завтра погода?',
 'Сделай потише.',
 'Сделай погромче.',
 'Останови музыку.',
 'Включи музыку.',
 'Открой дверь.',
 'Закрой шторы.',
 'Включи свет в спальне.',
 'Выключи свет на кухне.',
 'Сколько осталось до конца таймера?',
 'Я сейчас на кухне.',
 'Завтра утром будет дождь.',
 'Где лежат ключи?',
 'Мне нужно закончить работу.',
 'Пора идти спать.',
 'Пойдём гулять.',
 'Пожалуйста, принеси воды.',
 'Спасибо, всё готово.',
 'Мы сегодня смотрим кино.',
 'Кошка сидит у окна.',
 'Я открою приложение.',
 'Проверь сообщение.',
 'Пора приготовить ужин.',
 'Можешь закрыть окно?',
 'Телефон лежит на столе.',
 'Я вернусь через десять минут.',
 'Расскажи, что случилось.',
 'Это очень хорошая книжка.',
 'Давай поговорим об этом завтра.',
 'Она сказала привет и ушла.',
 'Компьютер не видит мышку.',
 'Коврик для мышки лежит в ящике.',
 'На картинке маленькая мышка.',
 'У Миши новая машинка.',
 'Мишка любит мёд.',
 'Машка машет рукой.',
 'Алекса.',
 'Окей, Набу.',
 'Алиса.',
 'Маруся.',
 'Стоп.')

VOICE_PINS = {'dmitri': {'revision': 'c10ece1aade47bb51c153c893d14e5bf8e5b7117',
            'repository': 'rhasspy/piper-voices',
            'license_reference': 'https://huggingface.co/rhasspy/piper-voices/blob/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/dmitri/medium/MODEL_CARD',
            'files': [{'path': 'voices/dmitri/ru_RU-dmitri-medium.onnx',
                       'url': 'https://huggingface.co/rhasspy/piper-voices/resolve/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/dmitri/medium/ru_RU-dmitri-medium.onnx',
                       'bytes': 63201294,
                       'sha256': 'f073356ebc4bd0f80c5af58df2953a5988bd5bdab1eb38635ce960b071fbefcb',
                       'upstream_lfs_sha256': 'f073356ebc4bd0f80c5af58df2953a5988bd5bdab1eb38635ce960b071fbefcb'},
                      {'path': 'voices/dmitri/ru_RU-dmitri-medium.onnx.json',
                       'url': 'https://huggingface.co/rhasspy/piper-voices/resolve/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/dmitri/medium/ru_RU-dmitri-medium.onnx.json',
                       'bytes': 4824,
                       'sha256': '667ef3117bc642c2892dff7690d8bdc8ca4228aeaa783b2dc1416df632855e0d',
                       'upstream_lfs_sha256': None},
                      {'path': 'voices/dmitri/MODEL_CARD',
                       'url': 'https://huggingface.co/rhasspy/piper-voices/resolve/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/dmitri/medium/MODEL_CARD',
                       'bytes': 277,
                       'sha256': '6d59c756776d57860232cea6484e1b2ea1fc1c8d2c3446ef246f706fd9875821',
                       'upstream_lfs_sha256': None}]},
 'denis': {'revision': 'c10ece1aade47bb51c153c893d14e5bf8e5b7117',
           'repository': 'rhasspy/piper-voices',
           'license_reference': 'https://huggingface.co/rhasspy/piper-voices/blob/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/denis/medium/MODEL_CARD',
           'files': [{'path': 'voices/denis/ru_RU-denis-medium.onnx',
                      'url': 'https://huggingface.co/rhasspy/piper-voices/resolve/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/denis/medium/ru_RU-denis-medium.onnx',
                      'bytes': 63201294,
                      'sha256': '15fab56e11a097858ee115545d0f697fc2a316c41a291a5362349fb870411b0a',
                      'upstream_lfs_sha256': '15fab56e11a097858ee115545d0f697fc2a316c41a291a5362349fb870411b0a'},
                     {'path': 'voices/denis/ru_RU-denis-medium.onnx.json',
                      'url': 'https://huggingface.co/rhasspy/piper-voices/resolve/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/denis/medium/ru_RU-denis-medium.onnx.json',
                      'bytes': 4823,
                      'sha256': '831c860dac0b5073eaa81610a0a638ec23d90a6cf8e5f871b4485c2cec3767c8',
                      'upstream_lfs_sha256': None},
                     {'path': 'voices/denis/MODEL_CARD',
                      'url': 'https://huggingface.co/rhasspy/piper-voices/resolve/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/denis/medium/MODEL_CARD',
                      'bytes': 276,
                      'sha256': '8b5d685dd80f8ad3f8dbbe1c56b16bb0809f00c144af3642dbcf3b707eb89c12',
                      'upstream_lfs_sha256': None}]},
 'irina': {'revision': 'c10ece1aade47bb51c153c893d14e5bf8e5b7117',
           'repository': 'rhasspy/piper-voices',
           'license_reference': 'https://huggingface.co/rhasspy/piper-voices/blob/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/irina/medium/MODEL_CARD',
           'files': [{'path': 'voices/irina/ru_RU-irina-medium.onnx',
                      'url': 'https://huggingface.co/rhasspy/piper-voices/resolve/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx',
                      'bytes': 63201294,
                      'sha256': '8ff38212d23da300bbe3705c645e6e5b9475f0bfde01558eb17813e22acaaaaa',
                      'upstream_lfs_sha256': '8ff38212d23da300bbe3705c645e6e5b9475f0bfde01558eb17813e22acaaaaa'},
                     {'path': 'voices/irina/ru_RU-irina-medium.onnx.json',
                      'url': 'https://huggingface.co/rhasspy/piper-voices/resolve/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx.json',
                      'bytes': 4765,
                      'sha256': 'c2ec28bb38e2b59e93b959b3e40348c1afebbd272f30fed5d41205d08e98a9d7',
                      'upstream_lfs_sha256': None},
                     {'path': 'voices/irina/MODEL_CARD',
                      'url': 'https://huggingface.co/rhasspy/piper-voices/resolve/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/irina/medium/MODEL_CARD',
                      'bytes': 271,
                      'sha256': 'f4fc2deb0e8c6219f29202b8dd06c9638c5ffd50ad5c6b2c90cf1aa59d507593',
                      'upstream_lfs_sha256': None}]},
 'ruslan': {'revision': 'c10ece1aade47bb51c153c893d14e5bf8e5b7117',
            'repository': 'rhasspy/piper-voices',
            'license_reference': 'https://huggingface.co/rhasspy/piper-voices/blob/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/ruslan/medium/MODEL_CARD',
            'files': [{'path': 'voices/ruslan/ru_RU-ruslan-medium.onnx',
                       'url': 'https://huggingface.co/rhasspy/piper-voices/resolve/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.onnx',
                       'bytes': 63201294,
                       'sha256': '72a5f88e0b20928064eb45d88e1daa21f8af62d18613580d32cbb4aed48dcf7f',
                       'upstream_lfs_sha256': '72a5f88e0b20928064eb45d88e1daa21f8af62d18613580d32cbb4aed48dcf7f'},
                      {'path': 'voices/ruslan/ru_RU-ruslan-medium.onnx.json',
                       'url': 'https://huggingface.co/rhasspy/piper-voices/resolve/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/ruslan/medium/ru_RU-ruslan-medium.onnx.json',
                       'bytes': 4882,
                       'sha256': '706a4fb17bc304abd07809b552deae615e64dcbffbfbd09854ba37ca59e88117',
                       'upstream_lfs_sha256': None},
                      {'path': 'voices/ruslan/MODEL_CARD',
                       'url': 'https://huggingface.co/rhasspy/piper-voices/resolve/c10ece1aade47bb51c153c893d14e5bf8e5b7117/ru/ru_RU/ruslan/medium/MODEL_CARD',
                       'bytes': 313,
                       'sha256': '28f5c0381c1234eb17bfd77e77f893b008948c29bc351fb811abd2d6a69e7662',
                       'upstream_lfs_sha256': None}]}}

BACKGROUND_PINS = [{'file': 'speech.zip',
  'revision': '0da95f94302ca2f4aae3b18fc6560fa6d2bba3d1',
  'sha256': '68b6b811b347b8321169f9e75ea2b9be73245943b4470af9532ca288d9f1b3cc',
  'bytes': 3183001091,
  'url': 'https://huggingface.co/datasets/kahrendt/microwakeword/resolve/0da95f94302ca2f4aae3b18fc6560fa6d2bba3d1/speech.zip'},
 {'file': 'no_speech.zip',
  'revision': '0da95f94302ca2f4aae3b18fc6560fa6d2bba3d1',
  'sha256': '722dbcc967275c64c9581ecb85729549830a9094ce605ee22b2ddab9dbabf3c8',
  'bytes': 2000317854,
  'url': 'https://huggingface.co/datasets/kahrendt/microwakeword/resolve/0da95f94302ca2f4aae3b18fc6560fa6d2bba3d1/no_speech.zip'},
 {'file': 'dinner_party.zip',
  'revision': '0da95f94302ca2f4aae3b18fc6560fa6d2bba3d1',
  'sha256': '18a0885d595ced7faa73736a8680206f5ba6e80113ca3e6ce43130e510aac18f',
  'bytes': 444310142,
  'url': 'https://huggingface.co/datasets/kahrendt/microwakeword/resolve/0da95f94302ca2f4aae3b18fc6560fa6d2bba3d1/dinner_party.zip'},
 {'file': 'dinner_party_eval.zip',
  'revision': '0da95f94302ca2f4aae3b18fc6560fa6d2bba3d1',
  'sha256': 'e08e23a5e654dd4415a1c41a4b6cd02d1f983c821512367ad937bac1aeed8299',
  'bytes': 82329019,
  'url': 'https://huggingface.co/datasets/kahrendt/microwakeword/resolve/0da95f94302ca2f4aae3b18fc6560fa6d2bba3d1/dinner_party_eval.zip'}]

LIBRISPEECH_PINS = [{'subset': 'dev-clean',
  'url': 'https://openslr.trmal.net/resources/12/dev-clean.tar.gz',
  'source_page': 'https://www.openslr.org/12',
  'published_md5': '42e2234ba48799c1f50f24a7926300a1',
  'checksum_url': 'https://openslr.trmal.net/resources/12/md5sum.txt',
  'license': 'CC BY 4.0',
  'license_url': 'https://creativecommons.org/licenses/by/4.0/',
  'md5': '42e2234ba48799c1f50f24a7926300a1',
  'sha256': '76f87d090650617fca0cac8f88b9416e0ebf80350acb97b343a85fa903728ab3',
  'bytes': 337926286},
 {'subset': 'test-clean',
  'url': 'https://openslr.trmal.net/resources/12/test-clean.tar.gz',
  'source_page': 'https://www.openslr.org/12',
  'published_md5': '32fa31d27d2e1cad72775fee3f4849a9',
  'checksum_url': 'https://openslr.trmal.net/resources/12/md5sum.txt',
  'license': 'CC BY 4.0',
  'license_url': 'https://creativecommons.org/licenses/by/4.0/',
  'md5': '32fa31d27d2e1cad72775fee3f4849a9',
  'sha256': '39fde525e59672dc6d1551919b1478f724438a95aa55f874b576be21967e6c23',
  'bytes': 346663984}]

SYNTHESIS_PACKAGES = {'numpy': '1.26.4',
 'onnxruntime': '1.30.0',
 'piper-tts': '1.3.0',
 'scipy': '1.17.1'}

# A different wake phrase is a new source population, never a relabelled pm-v1
# positive. Keep profile seeds, source prefixes and vocabulary reviewable here.
KOTIK_POSITIVES = (
    'Привет, котик.', 'Привет котик!', 'Привет, котик?',
    'Привет котик', 'Привет, Котик!', 'Привет, котик',
)

KOTIK_NEGATIVES = (
    'Привет, мышка.', 'Привет, Мышка!', 'Привет, Мишка.', 'Привет, Миша.',
    'Привет, кот.', 'Привет, котики.', 'Привет, котята.', 'Привет, котёнок.',
    'Привет, кошка.', 'Привет, Костя.', 'Привет, кофе.', 'Привет, Коля.',
    'Привет, Катя.', 'Привет, Котя.', 'Привет, компьютер.', 'Привет, кекс.',
    'Котик.', 'Кот.', 'Котики.', 'Котёнок.', 'Кошка.', 'Котята.', 'Кофе.',
    'Привет.', 'Привет всем.', 'Всем привет.', 'Привет, как дела?',
    'Передай привет котику.', 'Передай привет Косте.', 'Котик, привет.',
    'Котик сидит на диване.', 'Котик спит.', 'Котик, иди сюда.',
    'Где наш котик?', 'Погладь котика.', 'Котики играют.', 'Кот пьёт воду.',
    'Кошка сидит у окна.', 'Котёнок играет с мячом.', 'Приветливый кот.',
    'Я хочу кофе.', 'Сделай кофе, пожалуйста.', 'Принеси кофе.',
    'Кофе уже готов.', 'Кофейник стоит на столе.',
    'Добрый день.', 'Доброе утро.', 'Добрый вечер.', 'До свидания.',
    'Включи свет.', 'Выключи свет.', 'Поставь таймер на пять минут.',
    'Сколько сейчас времени?', 'Какая завтра погода?', 'Сделай потише.',
    'Сделай погромче.', 'Останови музыку.', 'Включи музыку.', 'Играй музыку.',
    'Включи радио.', 'Следующий трек.', 'Открой дверь.', 'Закрой шторы.',
    'Включи свет в спальне.', 'Выключи свет на кухне.',
    'Сколько осталось до конца таймера?', 'Я сейчас на кухне.',
    'Завтра утром будет дождь.', 'Где лежат ключи?',
    'Мне нужно закончить работу.', 'Пора идти спать.', 'Пойдём гулять.',
    'Пожалуйста, принеси воды.', 'Спасибо, всё готово.',
    'Мы сегодня смотрим кино.', 'Я открою приложение.', 'Проверь сообщение.',
    'Пора приготовить ужин.', 'Можешь закрыть окно?', 'Телефон лежит на столе.',
    'Я вернусь через десять минут.', 'Расскажи, что случилось.',
    'Давай поговорим об этом завтра.', 'Она сказала привет и ушла.',
    'Компьютер не видит мышку.', 'Алекса.', 'Окей, Набу.', 'Алиса.', 'Маруся.', 'Стоп.',
)

SYNTHESIS_PROFILES = {
    'pm-v1': {
        'version': 'pm-v1', 'model_id': 'privet_myshka_v1', 'wake_word': 'Привет, Мышка',
        'master_seed': MASTER_SEED, 'voices': VOICES,
        'positives': POSITIVES, 'negatives': NEGATIVES,
    },
    'pk-v1': {
        'version': 'pk-v1', 'model_id': 'privet_kotik_v1', 'wake_word': 'Привет, котик',
        'master_seed': 2026100204, 'voices': VOICES,
        'positives': KOTIK_POSITIVES, 'negatives': KOTIK_NEGATIVES,
        'pronunciation': 'Russian pri-VET, KO-tik: stress on the second syllable of привет '
                         'and the first syllable of котик. Plain Russian spelling; '
                         'Piper phonemes are retained for review. Human audition remains separate.',
    },
}


def synthesis_profile(name='pm-v1'):
    """Return a separate profile mapping, without mutating shared defaults."""
    if name not in SYNTHESIS_PROFILES:
        raise ValueError(f'Unknown synthesis profile: {name}')
    return dict(SYNTHESIS_PROFILES[name])


def require_profile_match(work, name):
    """Reject a conflicting model recipe or saved synthesis recipe before work."""
    import json
    from pathlib import Path
    work = Path(work)
    profile = synthesis_profile(name)
    model_recipe = work / 'recipe.json'
    if model_recipe.exists():
        cfg = json.loads(model_recipe.read_text())
        if cfg.get('synthesis_profile', 'pm-v1') != name:
            raise ValueError('Work directory model recipe selects another synthesis profile')
    saved = work / 'data-generation/recipe.json'
    if saved.exists():
        data = json.loads(saved.read_text())
        if data.get('version') != name:
            raise ValueError('Work directory already contains another synthesis profile; use a new directory')
        expected = {'master_seed': profile['master_seed'], 'voices': list(profile['voices']),
                    'positives': list(profile['positives']), 'negatives': list(profile['negatives'])}
        if any(data.get(key) != value for key, value in expected.items()):
            raise ValueError('Saved synthesis recipe seed, voices or vocabulary differs from the pinned profile')
        if 'wake_word' in data and data['wake_word'] != profile['wake_word']:
            raise ValueError('Saved synthesis source wake phrase differs from the pinned profile')
    return profile
