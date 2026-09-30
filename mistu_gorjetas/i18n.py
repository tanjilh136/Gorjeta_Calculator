"""English / Portuguese strings for the UI and the PDFs."""

from __future__ import annotations

from datetime import date, datetime

LANGUAGES = {"en": "English", "pt": "Português"}

_current = "pt"

STRINGS: dict[str, dict[str, str]] = {
    # ---------------------------------------------------------- navigation
    "nav.daily": {"en": "Daily Sheet", "pt": "Folha Diária"},
    "nav.staff": {"en": "Staff", "pt": "Funcionários"},
    "nav.records": {"en": "Records & Export", "pt": "Registos e Exportação"},
    "nav.settings": {"en": "Settings", "pt": "Definições"},
    "nav.about": {"en": "About", "pt": "Sobre"},
    # -------------------------------------------------------------- common
    "cash": {"en": "Cash", "pt": "Dinheiro"},
    "card": {"en": "Card", "pt": "Cartão"},
    "total": {"en": "Total", "pt": "Total"},
    "week": {"en": "Week", "pt": "Semana"},
    "staff": {"en": "Staff", "pt": "Funcionário"},
    "section": {"en": "Section", "pt": "Secção"},
    "status": {"en": "Status", "pt": "Estado"},
    "name": {"en": "Name", "pt": "Nome"},
    "date": {"en": "Date", "pt": "Data"},
    "day": {"en": "Day", "pt": "Dia"},
    "deduction": {"en": "Deduction", "pt": "Dedução"},
    "receivable": {"en": "Account Receivable", "pt": "Valor a Receber"},
    "yes": {"en": "Yes", "pt": "Sim"},
    "no": {"en": "No", "pt": "Não"},
    "ok": {"en": "OK", "pt": "OK"},
    "cancel": {"en": "Cancel", "pt": "Cancelar"},
    "save": {"en": "Save", "pt": "Guardar"},
    "discard": {"en": "Discard", "pt": "Descartar"},
    "error": {"en": "Error", "pt": "Erro"},
    "warning": {"en": "Warning", "pt": "Aviso"},
    "confirm": {"en": "Please confirm", "pt": "Confirmar"},
    "done": {"en": "Done", "pt": "Concluído"},
    "section.sala": {"en": "Sala", "pt": "Sala"},
    "section.cozinha": {"en": "Cozinha", "pt": "Cozinha"},
    "section.copa": {"en": "Copa", "pt": "Copa"},
    "section.other": {"en": "Other", "pt": "Outro"},
    "active": {"en": "Active", "pt": "Ativo"},
    "archived": {"en": "Archived", "pt": "Arquivado"},
    # -------------------------------------------------------- daily sheet
    "daily.title": {"en": "Daily Sheet", "pt": "Folha Diária"},
    "daily.today": {"en": "Today", "pt": "Hoje"},
    "daily.prev": {"en": "Previous day", "pt": "Dia anterior"},
    "daily.next": {"en": "Next day", "pt": "Dia seguinte"},
    "daily.cash_total": {"en": "Cash total (€)", "pt": "Total dinheiro (€)"},
    "daily.card_total": {"en": "Card total (€)", "pt": "Total cartão (€)"},
    "daily.present": {"en": "Present", "pt": "Presente"},
    "daily.present_count": {"en": "Present: {n} of {total}", "pt": "Presentes: {n} de {total}"},
    "daily.per_person": {
        "en": "Each present person: {cash} cash + {card} card = {total}",
        "pt": "Por pessoa presente: {cash} dinheiro + {card} cartão = {total}",
    },
    "daily.select_all": {"en": "Tick all", "pt": "Marcar todos"},
    "daily.select_none": {"en": "Untick all", "pt": "Desmarcar todos"},
    "daily.revert": {"en": "Undo changes", "pt": "Desfazer alterações"},
    "daily.status.saved": {"en": "✔ Saved", "pt": "✔ Guardado"},
    "daily.status.saved_at": {"en": "✔ Saved · {when}", "pt": "✔ Guardado · {when}"},
    "daily.status.unsaved": {"en": "● Unsaved changes", "pt": "● Alterações por guardar"},
    "daily.status.new": {"en": "○ New day – not saved yet", "pt": "○ Dia novo – ainda não guardado"},
    "daily.no_staff": {
        "en": "No active staff yet. Add staff members on the Staff page.",
        "pt": "Ainda não há funcionários ativos. Adicione-os na página Funcionários.",
    },
    "daily.err.nobody": {
        "en": "Nobody is marked present, but tip amounts were entered.\n\n"
              "Tick at least one person, or set both totals to 0.",
        "pt": "Ninguém está marcado como presente, mas foram introduzidos valores de gorjetas.\n\n"
              "Marque pelo menos uma pessoa, ou coloque os dois totais a 0.",
    },
    "daily.err.amount": {
        "en": "The {field} is not a valid amount.\n\nUse a format like 1234,56.",
        "pt": "O {field} não é um valor válido.\n\nUse um formato como 1234,56.",
    },
    "daily.saved_msg": {"en": "Day {date} saved.", "pt": "Dia {date} guardado."},
    "daily.unsaved_q": {
        "en": "The day {date} has unsaved changes.\n\nDo you want to save them?",
        "pt": "O dia {date} tem alterações por guardar.\n\nDeseja guardá-las?",
    },
    "daily.delete": {"en": "Delete day…", "pt": "Eliminar dia…"},
    "daily.delete_confirm": {
        "en": "Delete everything saved for {weekday} {date}?\n\n"
              "The cash and card totals and the attendance of this day will be removed. "
              "This cannot be undone.",
        "pt": "Eliminar tudo o que foi guardado para {weekday} {date}?\n\n"
              "Os totais de dinheiro e cartão e as presenças deste dia serão removidos. "
              "Esta ação não pode ser anulada.",
    },
    "daily.deleted": {"en": "Day {date} deleted.", "pt": "Dia {date} eliminado."},
    "daily.archived_tag": {"en": "(archived)", "pt": "(arquivado)"},
    # --------------------------------------------------------------- staff
    "staff.title": {"en": "Staff", "pt": "Funcionários"},
    "staff.hint": {
        "en": "Drag names to change the order. This order is used on the daily sheet and in all exports.",
        "pt": "Arraste os nomes para mudar a ordem. Esta ordem é usada na folha diária e em todas as exportações.",
    },
    "staff.add": {"en": "Add…", "pt": "Adicionar…"},
    "staff.edit": {"en": "Edit…", "pt": "Editar…"},
    "staff.archive": {"en": "Archive", "pt": "Arquivar"},
    "staff.restore": {"en": "Restore", "pt": "Restaurar"},
    "staff.delete": {"en": "Delete", "pt": "Eliminar"},
    "staff.up": {"en": "Move up", "pt": "Subir"},
    "staff.down": {"en": "Move down", "pt": "Descer"},
    "staff.dialog.add": {"en": "Add staff member", "pt": "Adicionar funcionário"},
    "staff.dialog.edit": {"en": "Edit staff member", "pt": "Editar funcionário"},
    "staff.err.name": {"en": "Please enter a name.", "pt": "Introduza um nome."},
    "staff.err.duplicate": {
        "en": "There is already a staff member called “{name}”.",
        "pt": "Já existe um funcionário chamado “{name}”.",
    },
    "staff.confirm.archive": {
        "en": "Archive {name}?\n\nThey will no longer appear on new daily sheets, "
              "but stay in exports for periods where they worked.",
        "pt": "Arquivar {name}?\n\nDeixa de aparecer nas novas folhas diárias, "
              "mas continua nas exportações dos períodos em que trabalhou.",
    },
    "staff.confirm.delete": {
        "en": "Delete {name} permanently?",
        "pt": "Eliminar {name} permanentemente?",
    },
    "staff.err.history": {
        "en": "{name} has saved days and cannot be deleted. Archive them instead.",
        "pt": "{name} tem dias guardados e não pode ser eliminado. Arquive-o em vez disso.",
    },
    "staff.count": {"en": "{active} active · {archived} archived", "pt": "{active} ativos · {archived} arquivados"},
    # ------------------------------------------------------------- records
    "records.title": {"en": "Records & Export", "pt": "Registos e Exportação"},
    "records.saved_days": {"en": "Saved days", "pt": "Dias guardados"},
    "records.year": {"en": "Year:", "pt": "Ano:"},
    "records.all_years": {"en": "All", "pt": "Todos"},
    "records.present": {"en": "Present", "pt": "Presentes"},
    "records.open_hint": {
        "en": "Double-click a day to open it in the Daily Sheet.",
        "pt": "Faça duplo clique num dia para o abrir na Folha Diária.",
    },
    "records.open": {"en": "Open in Daily Sheet", "pt": "Abrir na Folha Diária"},
    "records.summary": {
        "en": "{n} days · cash {cash} · card {card}",
        "pt": "{n} dias · dinheiro {cash} · cartão {card}",
    },
    "records.weekly": {"en": "Weekly export", "pt": "Exportação semanal"},
    "records.weekly.start": {"en": "Start (Monday)", "pt": "Início (segunda-feira)"},
    "records.weekly.end": {"en": "End (Sunday)", "pt": "Fim (domingo)"},
    "records.weekly.button": {"en": "Export Weekly PDF", "pt": "Exportar PDF Semanal"},
    "records.final": {"en": "Final export", "pt": "Exportação final"},
    "records.final.start": {"en": "From (Monday):", "pt": "De (segunda-feira):"},
    "records.final.end": {"en": "To (Sunday):", "pt": "Até (domingo):"},
    "records.final.weeks": {"en": "{n} weeks · deduction {pct}%", "pt": "{n} semanas · dedução {pct}%"},
    "records.final.button": {"en": "Final Export", "pt": "Exportação Final"},
    "records.final.err_range": {
        "en": "The end date must be after the start date.",
        "pt": "A data final tem de ser posterior à data inicial.",
    },
    "records.save_pdf": {"en": "Save PDF", "pt": "Guardar PDF"},
    "records.pdf_saved": {
        "en": "PDF saved:\n{path}\n\nOpen it now?",
        "pt": "PDF guardado:\n{path}\n\nAbrir agora?",
    },
    "records.pdf_error": {
        "en": "The PDF could not be saved:\n{error}\n\nIf the file is open in another program, close it and try again.",
        "pt": "Não foi possível guardar o PDF:\n{error}\n\nSe o ficheiro estiver aberto noutro programa, feche-o e tente novamente.",
    },
    "records.no_days": {"en": "No saved days yet.", "pt": "Ainda não há dias guardados."},
    # ------------------------------------------------------------ settings
    "settings.title": {"en": "Settings", "pt": "Definições"},
    "settings.general": {"en": "General", "pt": "Geral"},
    "settings.language": {"en": "Language:", "pt": "Idioma:"},
    "settings.deduction": {"en": "Deduction percentage:", "pt": "Percentagem de dedução:"},
    "settings.deduction_hint": {
        "en": "Used in the Final Export: Deduction = Total × this percentage.",
        "pt": "Usada na Exportação Final: Dedução = Total × esta percentagem.",
    },
    "settings.backup": {"en": "Backup", "pt": "Cópia de segurança"},
    "settings.backup_folder": {"en": "Backup folder:", "pt": "Pasta de cópias:"},
    "settings.browse": {"en": "Change…", "pt": "Alterar…"},
    "settings.reset_default": {"en": "Use Google Drive default", "pt": "Usar pasta do Google Drive"},
    "settings.backup_hint": {
        "en": "A backup is made automatically every time the app closes. "
              "One file per year (e.g. gorjetas_{year}.db), replaced on each backup.",
        "pt": "É feita uma cópia automaticamente sempre que a aplicação fecha. "
              "Um ficheiro por ano (ex.: gorjetas_{year}.db), substituído em cada cópia.",
    },
    "settings.backup_now": {"en": "Backup now", "pt": "Fazer cópia agora"},
    "settings.restore": {"en": "Restore from backup…", "pt": "Restaurar cópia…"},
    "settings.backup_ok": {"en": "Backup saved to:\n{path}", "pt": "Cópia guardada em:\n{path}"},
    "settings.backup_fail": {
        "en": "The backup folder could not be reached:\n{folder}\n\n{error}\n\n"
            "Your data is safe on this computer. Check that Google Drive is running, "
              "or choose another backup folder in Settings.",
        "pt": "Não foi possível aceder à pasta de cópias:\n{folder}\n\n{error}\n\n"
              "Os seus dados estão seguros neste computador. Verifique se o Google Drive "
              "está a funcionar, ou escolha outra pasta nas Definições.",
    },
    "settings.last_backup": {"en": "Last backup: {when}", "pt": "Última cópia: {when}"},
    "settings.never": {"en": "never", "pt": "nunca"},
    "settings.pick_folder": {"en": "Choose backup folder", "pt": "Escolher pasta de cópias"},
    "settings.pick_backup": {"en": "Choose backup file", "pt": "Escolher ficheiro de cópia"},
    "settings.restore_confirm": {
        "en": "Restore data from:\n{path}\n\nALL current data (staff, days, deduction %) will be "
              "replaced by the contents of this backup. A safety copy of the current data is kept.\n\nContinue?",
        "pt": "Restaurar dados de:\n{path}\n\nTODOS os dados atuais (funcionários, dias, % de dedução) "
              "serão substituídos pelo conteúdo desta cópia. É guardada uma cópia de segurança dos dados atuais.\n\nContinuar?",
    },
    "settings.restore_ok": {
        "en": "Data restored.\n\nThe previous data was kept in:\n{path}",
        "pt": "Dados restaurados.\n\nOs dados anteriores foram guardados em:\n{path}",
    },
    "settings.restore_invalid": {
        "en": "This file is not a valid Mistu Gorjetas backup.",
        "pt": "Este ficheiro não é uma cópia válida do Mistu Gorjetas.",
    },
    "settings.restore_fail": {"en": "Restore failed:\n{error}", "pt": "O restauro falhou:\n{error}"},
    "settings.retention": {"en": "Data retention", "pt": "Retenção de dados"},
    "settings.retention_hint": {
        "en": "Day records older than 5 years are removed automatically.",
        "pt": "Os registos de dias com mais de 5 anos são removidos automaticamente.",
    },
    "settings.delete_from": {"en": "From:", "pt": "De:"},
    "settings.delete_to": {"en": "To:", "pt": "Até:"},
    "settings.delete_button": {"en": "Delete data…", "pt": "Eliminar dados…"},
    "settings.delete_none": {
        "en": "There are no saved days between {start} and {end}.",
        "pt": "Não há dias guardados entre {start} e {end}.",
    },
    "settings.delete_confirm": {
        "en": "Permanently delete {n} saved day(s) from {start} to {end}?\n\n"
              "A backup is made first. This cannot be undone in the app.",
        "pt": "Eliminar permanentemente {n} dia(s) guardado(s) de {start} a {end}?\n\n"
              "É feita primeiro uma cópia de segurança. Esta ação não pode ser anulada na aplicação.",
    },
    "settings.delete_backup_fail": {
        "en": "Nothing was deleted, because the backup could not be made first:\n{error}\n\n"
              "Check the backup folder and try again.",
        "pt": "Nada foi eliminado, porque não foi possível fazer a cópia de segurança primeiro:\n{error}\n\n"
              "Verifique a pasta de cópias e tente novamente.",
    },
    "settings.delete_ok": {"en": "{n} day(s) deleted.", "pt": "{n} dia(s) eliminado(s)."},
    "settings.delete_err_range": {
        "en": "The end date must not be before the start date.",
        "pt": "A data final não pode ser anterior à data inicial.",
    },
    # --------------------------------------------------------------- about
    "about.title": {"en": "About", "pt": "Sobre"},
    "about.version": {"en": "Version {v}", "pt": "Versão {v}"},
    "about.description": {
        "en": "Daily tip sharing for Mistu Restaurante.",
        "pt": "Divisão diária de gorjetas do Mistu Restaurante.",
    },
    "about.data": {"en": "Data file:", "pt": "Ficheiro de dados:"},
    "about.credit": {"en": "Designed by Optivex Labs", "pt": "Designed by Optivex Labs"},
    # ----------------------------------------------------------- activation
    "act.title": {"en": "Activation", "pt": "Ativação"},
    "act.heading": {"en": "Enter the installation key", "pt": "Introduza a chave de instalação"},
    "act.text_new": {
        "en": "Mistu Gorjetas needs to be activated on this computer.",
        "pt": "O Mistu Gorjetas tem de ser ativado neste computador.",
    },
    "act.text_moved": {
        "en": "This installation was activated on a different computer, "
              "so it is locked. Enter the key to activate it on this computer.",
        "pt": "Esta instalação foi ativada noutro computador e está bloqueada. "
              "Introduza a chave para a ativar neste computador.",
    },
    "act.key": {"en": "Key:", "pt": "Chave:"},
    "act.show": {"en": "Show", "pt": "Mostrar"},
    "act.activate": {"en": "Activate", "pt": "Ativar"},
    "act.quit": {"en": "Quit", "pt": "Sair"},
    "act.wrong": {"en": "The key is not correct.", "pt": "A chave não está correta."},
    "act.write_fail": {
        "en": "The activation could not be saved:\n{error}",
        "pt": "Não foi possível guardar a ativação:\n{error}",
    },
    "act.not_configured": {
        "en": "This copy of Mistu Gorjetas was built without an installation key and cannot run.",
        "pt": "Esta cópia do Mistu Gorjetas foi criada sem chave de instalação e não pode ser executada.",
    },
    # ------------------------------------------------------------------ app
    "app.already_running": {
        "en": "Mistu Gorjetas is already open.",
        "pt": "O Mistu Gorjetas já está aberto.",
    },
    "app.unexpected": {
        "en": "An unexpected error occurred:\n{error}\n\nDetails were written to:\n{log}",
        "pt": "Ocorreu um erro inesperado:\n{error}\n\nOs detalhes foram escritos em:\n{log}",
    },
    "app.backup_closing": {"en": "Backing up…", "pt": "A fazer cópia de segurança…"},
    # ----------------------------------------------------------------- PDFs
    "pdf.weekly": {"en": "Weekly Export", "pt": "Exportação Semanal"},
    "pdf.final": {"en": "Final Export", "pt": "Exportação Final"},
    "pdf.generated": {"en": "Generated {when}", "pt": "Gerado em {when}"},
    "pdf.page": {"en": "Page {x}/{y}", "pt": "Página {x}/{y}"},
    "pdf.totals": {"en": "Total", "pt": "Total"},
    "pdf.week_total": {"en": "Week Total", "pt": "Total Semana"},
    "pdf.cash_total": {"en": "Cash Total", "pt": "Total Dinheiro"},
    "pdf.card_total": {"en": "Card Total", "pt": "Total Cartão"},
    "pdf.deduction_col": {"en": "Deduction ({pct}%)", "pt": "Dedução ({pct}%)"},
    "pdf.legend_weekly": {
        "en": "✗ = absent that day   — = no data saved for that day",
        "pt": "✗ = ausente nesse dia   — = sem dados guardados para esse dia",
    },
    "pdf.legend_final": {
        "en": "— = no data saved for that week",
        "pt": "— = sem dados guardados para essa semana",
    },
    "pdf.part": {"en": "Weeks {a}–{b} of {n}", "pt": "Semanas {a}–{b} de {n}"},
}

WEEKDAYS_SHORT = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "pt": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"],
}
WEEKDAYS_LONG = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "pt": ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira",
           "Sábado", "Domingo"],
}


def set_language(lang: str) -> None:
    global _current
    _current = lang if lang in LANGUAGES else "pt"


def language() -> str:
    return _current


def tr(key: str, **kwargs) -> str:
    entry = STRINGS.get(key)
    if entry is None:
        text = key
    else:
        text = entry.get(_current) or entry["en"]
    return text.format(**kwargs) if kwargs else text


def section_name(code: str) -> str:
    return tr(f"section.{code}") if f"section.{code}" in STRINGS else code


def fmt_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def fmt_day_month(d: date) -> str:
    return d.strftime("%d/%m")


def fmt_datetime(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y %H:%M")


def weekday_short(d: date) -> str:
    return WEEKDAYS_SHORT[_current][d.weekday()]


def weekday_long(d: date) -> str:
    return WEEKDAYS_LONG[_current][d.weekday()]
