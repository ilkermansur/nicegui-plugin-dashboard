def setup(ctx):
    @ctx.role("layout").page("/dashboard", lambda: ctx.t("title"), icon="extension")
    def page():
        ctx.role("theme").page_header(ctx.t("title"), ctx.t("description"))
