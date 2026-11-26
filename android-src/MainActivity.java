package br.com.somosservos.app;

import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.InsetDrawable;
import android.graphics.drawable.RippleDrawable;
import android.graphics.drawable.StateListDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Message;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.PopupMenu;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import androidx.activity.OnBackPressedCallback;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebViewClient;
import java.io.ByteArrayInputStream;
import java.text.DateFormat;
import java.util.Date;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

public class MainActivity extends BridgeActivity {
    private static final String HOST = "somosservos.blogspot.com";
    private static final String BLOG = "https://" + HOST;
    private static final String TODAY = BLOG + "/p/hoje.html?m=1";
    private static final String[] LABELS = {"Hoje", "Posts", "Boletim", "Aplicativos"};
    private static final String[] PAGES = {
        TODAY, BLOG + "/?m=1", BLOG + "/p/boletim.html?m=1",
        BLOG + "/p/aplicativos-servitas.html?m=1"
    };
    private static final int WINE = Color.rgb(90, 32, 41);
    private static final int PAPER = Color.rgb(246, 243, 236);
    private static final int BAR_CREAM = Color.rgb(255, 251, 244);
    private static final int TAB_TEXT = Color.rgb(88, 71, 64);
    private static final int BAR_LINE = Color.rgb(226, 213, 199);
    private static final String COMPACT_PAGE = """
        (() => {
          if (!document.getElementById('somos-servos-apk')) {
            const css = document.createElement('style');
            css.id = 'somos-servos-apk';
            css.textContent = '#header,#header-inner,.ss-brand-approved,.ss-skip,.content-inner>footer,.footer-outer{display:none!important}';
            document.head.append(css);
          }
          document.querySelectorAll('iframe[src]').forEach(frame => {
            const url = new URL(frame.src);
            if (url.protocol !== 'https:' || !url.hostname.endsWith('.sibforms.com')) return;
            const link = document.createElement('a');
            link.href = url.href;
            link.textContent = 'Abrir o formulário de inscrição no navegador';
            link.target = '_blank';
            link.rel = 'noopener';
            frame.replaceWith(link);
          });
        })()
        """;

    private WebView blog;
    private WebView local;
    private FrameLayout content;
    private ScrollView offline;
    private TextView offlineMessage;
    private Button share;
    private final Button[] tabs = new Button[LABELS.length];
    private SharedPreferences cache;
    private String failedUrl;
    private boolean showingLocal;
    private String openedDate;

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        if (getBridge() == null) return;

        cache = getSharedPreferences("hoje-offline", MODE_PRIVATE);
        local = getBridge().getWebView();
        setUpLayout();
        setUpLocalView();
        setUpBlog();

        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override public void handleOnBackPressed() {
                goBack();
            }
        });
        Bundle history = state == null ? null : state.getBundle("blogHistory");
        if (history == null || blog.restoreState(history) == null
                || getIntent().hasExtra("LocalNotificationId")) openPage(TODAY);
    }

    private void setUpLayout() {
        ViewGroup parent = (ViewGroup) local.getParent();
        parent.removeView(local);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BAR_CREAM);
        setContentView(root);
        ViewCompat.setOnApplyWindowInsetsListener(root, (view, insets) -> {
            var padding = insets.getInsets(WindowInsetsCompat.Type.systemBars()
                    | WindowInsetsCompat.Type.displayCutout() | WindowInsetsCompat.Type.ime());
            view.setPadding(padding.left, padding.top, padding.right, padding.bottom);
            var controller = ViewCompat.getWindowInsetsController(view);
            if (controller != null) {
                controller.setAppearanceLightStatusBars(true);
                controller.setAppearanceLightNavigationBars(true);
            }
            return insets;
        });

        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(dp(12), 0, dp(4), 0);
        TextView label = new TextView(this);
        label.setText("Somos Servos");
        label.setTextColor(WINE);
        label.setTextSize(18);
        toolbar.addView(label, new LinearLayout.LayoutParams(0, -2, 1));
        share = button("Compartilhar", this::sharePage);
        share.setEnabled(false);
        toolbar.addView(share);
        Button options = new Button(this, null, android.R.attr.borderlessButtonStyle);
        options.setText("Opções");
        options.setAllCaps(false);
        options.setTextColor(WINE);
        options.setMinHeight(dp(48));
        options.setOnClickListener(this::showOptions);
        toolbar.addView(options);
        root.addView(toolbar);
        root.addView(barDivider(), new LinearLayout.LayoutParams(-1, dp(1)));

        content = new FrameLayout(this);
        root.addView(content, new LinearLayout.LayoutParams(-1, 0, 1));
        blog = new WebView(this);
        content.addView(blog, new FrameLayout.LayoutParams(-1, -1));
        content.addView(local, new FrameLayout.LayoutParams(-1, -1));
        local.setVisibility(View.INVISIBLE);

        offline = new ScrollView(this);
        offline.setBackgroundColor(PAPER);
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(20), dp(20), dp(20), dp(20));
        panel.addView(button("Tentar de novo", () -> {
            if (failedUrl != null) openPage(failedUrl);
        }));
        offlineMessage = new TextView(this);
        offlineMessage.setTextSize(17);
        offlineMessage.setTextColor(Color.rgb(38, 34, 35));
        offlineMessage.setTextIsSelectable(true);
        panel.addView(offlineMessage);
        offline.addView(panel);
        content.addView(offline, new FrameLayout.LayoutParams(-1, -1));
        offline.setVisibility(View.GONE);

        root.addView(barDivider(), new LinearLayout.LayoutParams(-1, dp(1)));
        LinearLayout navigation = new LinearLayout(this);
        navigation.setPadding(dp(6), 0, dp(6), 0);
        for (int i = 0; i < LABELS.length; i++) {
            String url = PAGES[i];
            tabs[i] = button(LABELS[i], () -> openPage(url));
            styleTab(tabs[i]);
            navigation.addView(tabs[i], new LinearLayout.LayoutParams(0, -2, 1));
        }
        root.addView(navigation);
    }

    private View barDivider() {
        View line = new View(this);
        line.setBackgroundColor(BAR_LINE);
        return line;
    }

    private void styleTab(Button tab) {
        int[] selected = {android.R.attr.state_selected};
        int[] normal = {};
        tab.setTextColor(new ColorStateList(new int[][] {selected, normal},
                new int[] {BAR_CREAM, TAB_TEXT}));

        GradientDrawable active = new GradientDrawable();
        active.setColor(WINE);
        active.setCornerRadius(dp(16));
        GradientDrawable inactive = new GradientDrawable();
        inactive.setColor(Color.TRANSPARENT);
        inactive.setCornerRadius(dp(16));

        StateListDrawable background = new StateListDrawable();
        background.addState(selected, active);
        background.addState(normal, inactive);
        GradientDrawable mask = new GradientDrawable();
        mask.setColor(Color.WHITE);
        mask.setCornerRadius(dp(16));
        ColorStateList ripple = new ColorStateList(new int[][] {selected, normal},
                new int[] {Color.argb(56, 255, 251, 244), Color.argb(30, 90, 32, 41)});
        tab.setBackground(new InsetDrawable(new RippleDrawable(ripple, background, mask),
                dp(2), dp(5), dp(2), dp(5)));
        tab.setPadding(dp(3), 0, dp(3), 0);
    }

    private Button button(String label, Runnable action) {
        Button button = new Button(this, null, android.R.attr.borderlessButtonStyle);
        button.setText(label);
        button.setAllCaps(false);
        button.setTextColor(WINE);
        button.setMinHeight(dp(48));
        button.setOnClickListener(view -> action.run());
        return button;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private String localPage(String page) {
        return getBridge().getLocalUrl() + "/" + page;
    }

    private void setUpLocalView() {
        getBridge().setWebViewClient(new BridgeWebViewClient(getBridge()) {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (!request.isForMainFrame()) return super.shouldOverrideUrlLoading(view, request);
                Uri uri = request.getUrl();
                if (uri.toString().equals(localPage("index.html"))) {
                    openPage(TODAY);
                    return true;
                }
                if (!Uri.parse(getBridge().getLocalUrl()).getAuthority().equals(uri.getAuthority())
                        || !"https".equals(uri.getScheme())) {
                    openBrowser(uri);
                    return true;
                }
                return super.shouldOverrideUrlLoading(view, request);
            }
        });
    }

    private void setUpBlog() {
        // O Blogger tem sua própria WebView e não recebe a ponte de plugins do Capacitor.
        var settings = blog.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setSupportMultipleWindows(true);
        settings.setUserAgentString(settings.getUserAgentString() + " SomosServosAndroid/1.0");
        blog.setDownloadListener((url, agent, disposition, type, length) -> openBrowser(Uri.parse(url)));

        blog.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (isBlog(uri) || (!request.isForMainFrame() && !request.hasGesture())) return false;
                openBrowser(uri);
                return true;
            }

            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                String host = request.getUrl().getHost();
                if (!request.isForMainFrame() && host != null && host.endsWith(".sibforms.com")
                        && request.getUrl().getPath() != null && request.getUrl().getPath().startsWith("/serve/")) {
                    return new WebResourceResponse("text/html", "UTF-8",
                            new ByteArrayInputStream(new byte[0]));
                }
                return null;
            }

            @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap icon) {
                failedUrl = null;
                offline.setVisibility(View.GONE);
                if (!showingLocal) blog.setVisibility(View.VISIBLE);
                share.setEnabled(false);
                selectTab(url);
            }

            @Override public void onPageCommitVisible(WebView view, String url) {
                if (isBlog(Uri.parse(url)) && failedUrl == null) view.evaluateJavascript(COMPACT_PAGE, null);
            }

            @Override public void onPageFinished(WebView view, String url) {
                if (failedUrl != null || !url.equals(view.getUrl()) || !isBlog(Uri.parse(url))) return;
                view.evaluateJavascript(COMPACT_PAGE, null);
                share.setEnabled(!showingLocal);
                selectTab(url);
                if (isToday(url)) {
                    openedDate = dayStamp();
                    saveToday(view);
                }
            }

            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) showOffline(request.getUrl().toString());
            }

            @Override public void onReceivedHttpError(WebView view, WebResourceRequest request,
                    WebResourceResponse response) {
                if (request.isForMainFrame()) showOffline(request.getUrl().toString());
            }
        });

        blog.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onCreateWindow(WebView view, boolean dialog,
                    boolean userGesture, Message result) {
                if (!userGesture) return false;
                WebView popup = new WebView(MainActivity.this);
                Runnable cleanup = popup::destroy;
                popup.setWebViewClient(new WebViewClient() {
                    @Override public boolean shouldOverrideUrlLoading(WebView child, WebResourceRequest request) {
                        Uri uri = request.getUrl();
                        if ("about:blank".equals(uri.toString())) return false;
                        content.removeCallbacks(cleanup);
                        content.post(cleanup);
                        if (isBlog(uri)) openPage(uri.toString());
                        else openBrowser(uri);
                        return true;
                    }
                });
                content.postDelayed(cleanup, 15000);
                ((WebView.WebViewTransport) result.obj).setWebView(popup);
                result.sendToTarget();
                return true;
            }
        });
    }

    private static boolean isBlog(Uri uri) {
        return "https".equals(uri.getScheme()) && HOST.equals(uri.getHost())
                && (uri.getPort() == -1 || uri.getPort() == 443) && uri.getUserInfo() == null;
    }

    private static boolean isToday(String url) {
        if (url == null) return false;
        Uri uri = Uri.parse(url);
        return isBlog(uri) && "/p/hoje.html".equals(uri.getPath());
    }

    private void openBrowser(Uri uri) {
        String scheme = uri.getScheme();
        if (!"https".equals(scheme) && !"http".equals(scheme) && !"mailto".equals(scheme)
                && !"tel".equals(scheme)) return;
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW, uri).addCategory(Intent.CATEGORY_BROWSABLE);
            if ("https".equals(scheme) || "http".equals(scheme)) {
                intent.setSelector(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_APP_BROWSER));
            }
            startActivity(intent);
        } catch (ActivityNotFoundException error) {
            Toast.makeText(this, "Nenhum aplicativo disponível para abrir o link.", Toast.LENGTH_LONG).show();
        }
    }

    private void openPage(String url) {
        boolean wasLocal = showingLocal;
        if (wasLocal) closeLocal();
        if (failedUrl != null || !url.equals(blog.getUrl()) || (isToday(url) && !dayStamp().equals(openedDate))) {
            if (url.equals(blog.getUrl())) blog.reload();
            else blog.loadUrl(url);
        }
    }

    private void selectTab(String url) {
        String path = Uri.parse(url).getPath();
        for (int i = 0; i < tabs.length; i++) {
            boolean active = !showingLocal && (i == 1
                    ? "/".equals(path) || (path != null && (path.startsWith("/search") || path.matches("/\\d{4}/.*")))
                    : Uri.parse(PAGES[i]).getPath().equals(path));
            tabs[i].setSelected(active);
        }
    }

    private void showOptions(View anchor) {
        PopupMenu menu = new PopupMenu(this, anchor);
        menu.getMenu().add("Lembrete diário às 7h").setOnMenuItemClickListener(item -> {
            showLocal("android-shell.html");
            return true;
        });
        menu.getMenu().add("Recursos offline").setOnMenuItemClickListener(item -> {
            showLocal("recursos.html");
            return true;
        });
        menu.show();
    }

    private void showLocal(String page) {
        showingLocal = true;
        share.setEnabled(false);
        offline.setVisibility(View.GONE);
        blog.setVisibility(View.INVISIBLE);
        local.setVisibility(View.VISIBLE);
        local.loadUrl(localPage(page));
        if (blog.getUrl() != null) selectTab(blog.getUrl());
    }

    private void closeLocal() {
        showingLocal = false;
        local.setVisibility(View.INVISIBLE);
        local.loadUrl(localPage("android-shell.html"));
        blog.setVisibility(View.VISIBLE);
        String url = blog.getUrl();
        if (failedUrl != null) showOffline(failedUrl);
        else share.setEnabled(url != null && isBlog(Uri.parse(url)));
        if (url != null) selectTab(url);
    }

    private void goBack() {
        if (showingLocal) {
            var history = local.copyBackForwardList();
            int index = history.getCurrentIndex();
            if (index > 0 && !localPage("android-shell.html").equals(history.getItemAtIndex(index).getUrl())
                    && !localPage("android-shell.html").equals(history.getItemAtIndex(index - 1).getUrl())) {
                local.goBack();
            } else {
                closeLocal();
            }
        } else if (blog.canGoBack()) {
            blog.goBack();
        } else if (!isToday(failedUrl != null ? failedUrl : blog.getUrl())) {
            openPage(TODAY);
        } else {
            finish();
        }
    }

    private void sharePage() {
        String page = blog.getUrl();
        if (page == null || failedUrl != null) return;
        blog.evaluateJavascript("JSON.stringify([document.querySelector('link[rel=canonical]')?.href,"
                + "(location.pathname.endsWith('.html') ? document.querySelector('.post-title.entry-title')?.innerText : null)"
                + " || document.title])", result -> {
            if (showingLocal || !page.equals(blog.getUrl())) return;
            String url = page;
            String title = blog.getTitle();
            try {
                JSONArray data = new JSONArray(new JSONArray("[" + result + "]").getString(0));
                String canonical = data.optString(0);
                // As listagens de marcador e busca podem declarar a capa como link canônico.
                if (isBlog(Uri.parse(canonical))
                        && Uri.parse(page).getPath().equals(Uri.parse(canonical).getPath())
                        && Uri.parse(page).getQueryParameter("q") == null) url = canonical;
                title = data.optString(1, title);
            } catch (JSONException ignored) {
                // A WebView pode já ter iniciado outra navegação.
            }
            Uri uri = Uri.parse(url);
            Uri.Builder clean = uri.buildUpon().clearQuery();
            for (String key : uri.getQueryParameterNames()) {
                if ("m".equals(key) || "app".equals(key)) continue;
                for (String value : uri.getQueryParameters(key)) clean.appendQueryParameter(key, value);
            }
            String data = "{title:" + JSONObject.quote(title) + ",text:" + JSONObject.quote(title)
                    + ",url:" + JSONObject.quote(clean.toString()) + ",dialogTitle:'Compartilhar'}";
            local.evaluateJavascript("Capacitor.Plugins.Share.share(" + data + ")", null);
        });
    }

    private void saveToday(WebView view) {
        view.evaluateJavascript("document.querySelector('#hs-dia .hs-titulo') ? "
                + "document.querySelector('#hs-dia').innerText + '\\n\\n' + "
                + "(document.querySelector('#hs-prox')?.innerText || '') : null", value -> {
            if (failedUrl != null || !isToday(view.getUrl())) return;
            try {
                JSONArray result = new JSONArray("[" + value + "]");
                if (!result.isNull(0)) {
                    String text = result.getString(0).trim();
                    if (text.length() > 0 && text.length() <= 15000) {
                        cache.edit().putString("text", text).putString("date", dayStamp()).apply();
                    }
                }
            } catch (JSONException ignored) {
                // Preserva a última celebração salva se a estrutura da página mudar.
            }
        });
    }

    private void showOffline(String url) {
        failedUrl = url;
        share.setEnabled(false);
        if (showingLocal) return;
        blog.setVisibility(View.INVISIBLE);
        String message = "Não foi possível abrir esta página. Verifique a conexão e tente de novo.";
        String saved = isToday(url) ? cache.getString("text", null) : null;
        if (saved != null) {
            message += "\n\nÚltima celebração salva (" + cache.getString("date", "") + ")\n\n" + saved;
        }
        offlineMessage.setText(message);
        offline.scrollTo(0, 0);
        offline.setVisibility(View.VISIBLE);
    }

    private static String dayStamp() {
        return DateFormat.getDateInstance(DateFormat.SHORT, java.util.Locale.forLanguageTag("pt-BR"))
                .format(new Date());
    }

    @Override public void onResume() {
        super.onResume();
        if (local != null) local.evaluateJavascript(
                "window.dispatchEvent(new Event('somos-servos-resume'))", null);
        if (blog != null && !showingLocal && isToday(blog.getUrl())
                && openedDate != null && !dayStamp().equals(openedDate)) blog.reload();
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        if (blog != null && intent != null && intent.hasExtra("LocalNotificationId")) openPage(TODAY);
    }

    @Override public void onSaveInstanceState(Bundle state) {
        super.onSaveInstanceState(state);
        if (blog == null) return;
        Bundle history = new Bundle();
        blog.saveState(history);
        state.putBundle("blogHistory", history);
    }

    @Override public void onDestroy() {
        if (blog != null) {
            content.removeView(blog);
            blog.destroy();
        }
        super.onDestroy();
    }
}
