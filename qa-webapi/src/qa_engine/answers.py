from typing import Any, List, Dict, Optional

from .intents import IntentParam, Intent, UnknownIntent


class Answer:
    def __init__(self,
                 intent: Optional[Intent] = None,
                 answer: Optional[str] = None,
                 answer_format: Optional[str] = None):

        self.intent = intent
        self.answer = answer
        self.answer_format = answer_format

    @staticmethod
    def get_variables(params: List[IntentParam]) -> List[Dict[str, Any]]:
        def to_dict(param):
            if param and not param.is_empty:
                return {
                    'value': param.orig_value,
                    'meaning': param.meaning
                }
            else:
                return {}

        return [p for p in [to_dict(p) for p in params] if p]

    @staticmethod
    def get_probable_variables(params: List[IntentParam]) -> List[Dict[str, Any]]:
        def to_dict(param, add_all=False):
            if param and (param.is_missed() or add_all):
                return {
                    'value': param.orig_value,
                    'meaning': param.meaning,
                    'alternative': to_dict(param.alternative, add_all=True)
                }
            else:
                return None

        return [p for p in [to_dict(p) for p in params] if p]

    def get_details(self) -> Dict[str, str]:
        result = {
            'answer_type': self.__class__.__name__
        }

        if self.intent is not None:
            result['question'] = self.intent.get_natural_language_question()
            result['variables'] = self.get_variables(self.intent.get_params())

        if self.answer is not None:
            result['answer'] = self.answer
            result['answer_format'] = self.answer_format

        if self.get_intention() is not None:
            result['intention'] = self.get_intention()

        return result

    def get_question(self) -> Optional[str]:
        if self.intent is not None:
            return self.intent.get_natural_language_question()
        else:
            return None

    def get_intention(self) -> Optional[str]:
        if self.intent is not None:
            return self.intent.nl_description()
        else:
            return None


class NotUnderstandAnswer(Answer):
    def __init__(self, intent: UnknownIntent):
        super().__init__(intent=intent, answer=None, answer_format=None)
        self.unknown_intent = intent

    def get_details(self):
        result = super().get_details()

        if self.unknown_intent.get_probable_intent() is not None:
            result.update({
                'probable_intention': self.intent.get_probable_intent().nl_description(),
                'probable_variables': self.get_probable_variables(self.intent.get_probable_intent().get_params())
            })

        return result

    def get_intention(self) -> Optional[str]:
        return None


class KnownAnswer(Answer):
    def __init__(self, intent: Intent, answer: str, answer_format: str = 'application/rdf+xml'):
        super().__init__(intent=intent, answer=answer, answer_format=answer_format)


class CanNotAnswer(Answer):
    def __init__(self, intent: Intent):
        super().__init__(intent=intent, answer=None, answer_format=None)
