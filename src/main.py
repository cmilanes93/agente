"""Punto de entrada: chat de consola con el agente."""

from dotenv import load_dotenv

from src.agent import Agent


def main() -> None:
    load_dotenv()
    agent = Agent()

    print("Agente listo. Escribí 'salir' para terminar.\n")
    while True:
        user_text = input("Vos: ").strip()
        if user_text.lower() in {"salir", "exit", "quit"}:
            break
        if not user_text:
            continue

        reply = agent.send(user_text)
        print(f"Agente: {reply}\n")


if __name__ == "__main__":
    main()
