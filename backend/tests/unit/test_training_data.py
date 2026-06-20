"""Unit-тесты: Training — структура данных моделей."""

from app.models.training import FAQ, ImportantNote, Instruction, TrainingVideo


class TestTrainingModels:
    """Проверяем что модели имеют нужные поля."""

    def test_faq_has_fields(self):
        cols = {c.key for c in FAQ.__table__.columns}
        assert "question" in cols
        assert "answer" in cols
        assert "order" in cols

    def test_video_has_fields(self):
        cols = {c.key for c in TrainingVideo.__table__.columns}
        assert "title" in cols
        assert "thumbnail_url" in cols
        assert "order" in cols

    def test_instruction_has_fields(self):
        cols = {c.key for c in Instruction.__table__.columns}
        assert "title" in cols
        assert "steps" in cols
        assert "order" in cols

    def test_important_note_has_fields(self):
        cols = {c.key for c in ImportantNote.__table__.columns}
        assert "title" in cols
        assert "description" in cols
        assert "order" in cols
