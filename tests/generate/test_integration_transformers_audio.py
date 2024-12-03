from io import BytesIO
from urllib.request import urlopen

import librosa
import pytest
import torch
from transformers import AutoProcessor, Qwen2AudioForConditionalGeneration

import outlines
from outlines.models.transformers_audio import transformers_audio

AUDIO_URLS = [
    "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen2-Audio/audio/glass-breaking-151256.mp3",
    "https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen2-Audio/audio/f2641_0_throatclearing.wav",
]
QWEN2_AUDIO_SAMPLING_RATE = 16000

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def audio_from_url(url):
    audio_byte_stream = BytesIO(urlopen(url).read())
    return librosa.load(audio_byte_stream, sr=QWEN2_AUDIO_SAMPLING_RATE)[0]


@pytest.fixture(scope="session")
def model(tmp_path_factory):
    return transformers_audio(
        "Qwen/Qwen2-Audio-7B-Instruct",
        model_class=Qwen2AudioForConditionalGeneration,
        device="cuda",
        model_kwargs=dict(
            torch_dtype=torch.bfloat16,
            load_in_4bit=True,
            low_cpu_mem_usage=True,
        ),
    )


@pytest.fixture(scope="session")
def processor(tmp_path_factory):
    return AutoProcessor.from_pretrained("Qwen/Qwen2-Audio-7B-Instruct")


def test_single_audio_text_gen(model, processor):
    conversation = [
        {
            "role": "user",
            "content": [
                {"audio"},
                {"type": "text", "text": "What's that sound?"},
            ],
        },
    ]
    generator = outlines.generate.text(model)
    sequence = generator(
        processor.apply_chat_template(conversation),
        [audio_from_url(AUDIO_URLS[0])],
        seed=10000,
        max_tokens=10,
    )
    assert isinstance(sequence, str)


def test_multi_audio_text_gen(model, processor):
    """If the length of audio tags and number of audios we pass are > 1 and equal,
    we should yield a successful generation.
    """
    conversation = [
        {
            "role": "user",
            "content": [{"audio"} for _ in range(len(AUDIO_URLS))]
            + [
                {
                    "type": "text",
                    "text": "Did a human make one of the audio recordings?",
                }
            ],
        },
    ]
    generator = outlines.generate.text(model)
    sequence = generator(
        processor.apply_chat_template(conversation),
        [audio_from_url(url) for url in AUDIO_URLS],
        seed=10000,
        max_tokens=10,
    )
    assert isinstance(sequence, str)


def test_mismatched_audio_text_gen(model, processor):
    """If the length of audio tags and number of audios we pass are unequal,
    we should raise an error.
    """
    generator = outlines.generate.text(model)

    conversation = [
        {
            "role": "user",
            "content": [
                {"audio"},
                {"type": "text", "text": "I'm passing 2 audios, but only 1 audio tag"},
            ],
        },
    ]
    with pytest.raises(RuntimeError):
        _ = generator(
            processor.apply_chat_template(conversation),
            [audio_from_url(i) for i in AUDIO_URLS],
            seed=10000,
            max_tokens=10,
        )

    conversation = [
        {
            "role": "user",
            "content": [
                {"audio"},
                {"audio"},
                {"type": "text", "text": "I'm passing 2 audio tags, but only 1 audio"},
            ],
        },
    ]
    with pytest.raises(ValueError):
        _ = generator(
            processor.apply_chat_template(conversation),
            [audio_from_url(AUDIO_URLS[0])],
            seed=10000,
            max_tokens=10,
        )


def test_single_audio_choice(model, processor):
    conversation = [
        {
            "role": "user",
            "content": [
                {"audio"},
                {"type": "text", "text": "What is this?"},
            ],
        },
    ]
    choices = ["dog barking", "glass breaking"]
    generator = outlines.generate.choice(model, choices)
    sequence = generator(
        processor.apply_chat_template(conversation),
        [audio_from_url(AUDIO_URLS[0])],
        seed=10000,
        max_tokens=10,
    )
    assert isinstance(sequence, str)
    assert sequence in choices
