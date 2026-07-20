import "./App.css";

const conversations = ["Nova conversa"];

const suggestions = [
  {
    icon: "✦",
    title: "Cuidados na gestação",
    description: "Quais cuidados são importantes durante a gravidez?",
  },
  {
    icon: "◌",
    title: "Preparação para o parto",
    description: "Como preparar a mala da maternidade?",
  },
  {
    icon: "♡",
    title: "Cuidados com o bebê",
    description: "Como cuidar do bebê nos primeiros dias?",
  },
];

function App() {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div className="brand">
            <div className="brand-logo">M</div>

            <div>
              <strong>Mater AI</strong>
              <span>Assistente maternal</span>
            </div>
          </div>

          <button
            className="collapse-button"
            type="button"
            aria-label="Recolher menu"
          >
            ‹
          </button>
        </div>

        <button className="new-chat-button" type="button">
          <span>＋</span>
          Nova conversa
        </button>

        <div className="sidebar-section">
          <span className="sidebar-section-title">Conversas recentes</span>

          <nav className="conversation-list">
            {conversations.map((conversation) => (
              <button
                className="conversation-item conversation-item-active"
                type="button"
                key={conversation}
              >
                <span className="conversation-icon">◫</span>

                <span className="conversation-name">
                  {conversation}
                </span>

                <span className="conversation-options">•••</span>
              </button>
            ))}
          </nav>
        </div>

        <div className="sidebar-footer">
          <button className="sidebar-footer-button" type="button">
            <span>?</span>
            Central de ajuda
          </button>

          <button className="user-card" type="button">
            <div className="user-avatar">KB</div>

            <div className="user-info">
              <strong>Kaique Batista</strong>
              <span>Conta pessoal</span>
            </div>

            <span className="user-options">•••</span>
          </button>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="agent-info">
            <div className="agent-avatar">✦</div>

            <div>
              <div className="agent-name">
                <h1>Agente Mater AI</h1>

                <span className="status-badge">
                  <span className="status-dot" />
                  Online
                </span>
              </div>

              <p>Assistente para dúvidas sobre maternidade</p>
            </div>
          </div>

          <div className="topbar-actions">
            <button
              className="icon-button"
              type="button"
              aria-label="Pesquisar"
            >
              ⌕
            </button>

            <button
              className="icon-button"
              type="button"
              aria-label="Mais opções"
            >
              •••
            </button>
          </div>
        </header>

        <section className="chat-container chat-container-empty">
          <div className="chat-content">
            <section className="welcome-section">
              <div className="welcome-icon">✦</div>

              <h2>Olá! Como posso ajudar?</h2>

              <p>
                Tire suas dúvidas sobre gestação, parto, pós-parto e os
                primeiros cuidados com o bebê.
              </p>
            </section>

            <section className="suggestion-grid">
              {suggestions.map((suggestion) => (
                <button
                  className="suggestion-card"
                  type="button"
                  key={suggestion.title}
                >
                  <div className="suggestion-icon">
                    {suggestion.icon}
                  </div>

                  <div>
                    <strong>{suggestion.title}</strong>
                    <p>{suggestion.description}</p>
                  </div>

                  <span className="suggestion-arrow">→</span>
                </button>
              ))}
            </section>
          </div>
        </section>

        <footer className="composer-container">
          <div className="composer">
            <button
              className="attachment-button"
              type="button"
              aria-label="Adicionar arquivo"
            >
              ＋
            </button>

            <textarea
              aria-label="Digite sua pergunta"
              placeholder="Digite sua pergunta..."
              rows={1}
            />

            <div className="composer-actions">
              <button
                className="voice-button"
                type="button"
                aria-label="Enviar áudio"
              >
                ◉
              </button>

              <button
                className="send-button"
                type="button"
                aria-label="Enviar mensagem"
              >
                ↑
              </button>
            </div>
          </div>

          <p className="disclaimer">
            O Mater AI pode cometer erros. Informações médicas devem ser
            confirmadas com um profissional de saúde.
          </p>
        </footer>
      </main>
    </div>
  );
}

export default App;