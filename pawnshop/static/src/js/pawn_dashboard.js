/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class PawnDashboardClient extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loading: true, branchId: false, data: null });
        onWillStart(async () => {
            await this.fetch();
        });
        onMounted(() => {
            this._renderCharts();
        });
        this._charts = { loan: null, trend: null };
    }

    async fetch() {
        this.state.loading = true;
        const data = await this.orm.call("pawn.dashboard", "get_metrics", [], { branch_id: this.state.branchId });
        this.state.data = data;
        this.state.loading = false;
        // Give the DOM a tick to render then draw charts
        setTimeout(() => this._renderCharts(), 0);
    }

    // Navigation helpers
    async openTickets() {
        await this.action.doAction("pawnshop.action_pawn_ticket");
    }
    async openDueToday() {
        await this.action.doAction("pawnshop.action_pawn_ticket", {
            additional_context: {},
            domain: [["date_maturity", "=", this.state.data.today], ["state", "in", ["active", "renewed"]]],
        });
    }
    async openOverdue() {
        await this.action.doAction("pawnshop.action_pawn_ticket", {
            domain: [["date_maturity", "<", this.state.data.today], ["state", "in", ["active", "renewed"]]],
        });
    }
    async openReportLoanBook() {
        await this.action.doAction("pawnshop.action_pawn_loan_book_report");
    }

    _renderCharts() {
        if (!this.state.data) return;
        // Loan composition (doughnut)
        const loanEl = document.getElementById("loanPie");
        if (loanEl && window.Chart) {
            if (this._charts.loan) this._charts.loan.destroy();
            const buckets = this.state.data.loan_book_buckets || {};
            const labels = ["Current", "Due Soon", "Grace", "Overdue", "Matured"];
            const data = [
                buckets.current || 0,
                buckets.due_soon || 0,
                buckets.grace || 0,
                buckets.overdue || 0,
                buckets.matured || 0,
            ];
            this._charts.loan = new window.Chart(loanEl.getContext("2d"), {
                type: "doughnut",
                data: {
                    labels,
                    datasets: [{
                        data,
                        backgroundColor: ["#3b82f6", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6"],
                        borderWidth: 0,
                    }],
                },
                options: { plugins: { legend: { position: "bottom" } } },
            });
        }

        // 14-day trend (line)
        const trendEl = document.getElementById("trendLine");
        if (trendEl && window.Chart) {
            if (this._charts.trend) this._charts.trend.destroy();
            const t = this.state.data.trend || { labels: [], created: [], redeemed: [], renewed: [] };
            this._charts.trend = new window.Chart(trendEl.getContext("2d"), {
                type: "line",
                data: {
                    labels: t.labels,
                    datasets: [
                        { label: "Created", data: t.created, borderColor: "#3b82f6", backgroundColor: "#3b82f633", tension: 0.3 },
                        { label: "Redeemed", data: t.redeemed, borderColor: "#10b981", backgroundColor: "#10b98133", tension: 0.3 },
                        { label: "Renewed", data: t.renewed, borderColor: "#f59e0b", backgroundColor: "#f59e0b33", tension: 0.3 },
                    ],
                },
                options: { responsive: true, plugins: { legend: { position: "bottom" } }, scales: { y: { beginAtZero: true, precision: 0 } } },
            });
        }
    }
}

PawnDashboardClient.template = "pawnshop.PawnDashboardTemplate";

registry.category("actions").add("pawnshop_dashboard", PawnDashboardClient);
