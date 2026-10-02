import ollama

from config import OLLAMA_HOST


class Agente:
    def __init__(self, nombre, modelo, system_prompt, temperatura=None):
        self.nombre = nombre
        self.modelo = modelo
        self.temperatura = temperatura
        self.historial = [{"role": "system", "content": system_prompt}]
        self.cliente = ollama.Client(host=OLLAMA_HOST)

    def responder(self, mensaje):
        self.historial.append({"role": "user", "content": mensaje})
        opciones = {"num_predict": 200}
        if self.temperatura is not None:
            opciones["temperature"] = self.temperatura
        resp = self.cliente.chat(
            model=self.modelo, messages=self.historial, options=opciones
        )
        texto = resp["message"]["content"].strip()
        self.historial.append({"role": "assistant", "content": texto})
        return texto
