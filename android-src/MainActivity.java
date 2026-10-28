package br.com.somosservos.app;

import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Message;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.BridgeWebChromeClient;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        WebView webView = getBridge().getWebView();
        // Os feeds do Blogger usam target="_blank", inclusive dentro do iframe.
        webView.getSettings().setSupportMultipleWindows(true);
        webView.setWebChromeClient(new BridgeWebChromeClient(getBridge()) {
            @Override
            public boolean onCreateWindow(WebView view, boolean dialog,
                    boolean userGesture, Message resultMsg) {
                if (!userGesture) return false;
                // O HitTestResult do pai não contém o destino de links em iframes.
                // O transporte entrega o URL real à WebView temporária, sem exibi-la.
                WebView popup = new WebView(MainActivity.this);
                popup.setWebViewClient(new WebViewClient() {
                    private boolean handled;

                    private boolean open(String url) {
                        if (handled) return true;
                        if ("about:blank".equals(url)) return false;
                        handled = true;
                        Uri uri = Uri.parse(url);
                        String scheme = uri.getScheme();
                        if ("https".equalsIgnoreCase(scheme)
                                || "http".equalsIgnoreCase(scheme)) {
                            try {
                                Intent intent = new Intent(Intent.ACTION_VIEW, uri);
                                intent.addCategory(Intent.CATEGORY_BROWSABLE);
                                startActivity(intent);
                            } catch (ActivityNotFoundException error) {
                                Toast.makeText(MainActivity.this,
                                        "Nenhum navegador disponível para abrir o link.",
                                        Toast.LENGTH_LONG).show();
                            }
                        }
                        popup.post(popup::destroy);
                        return true;
                    }

                    @Override
                    public boolean shouldOverrideUrlLoading(WebView child,
                            WebResourceRequest request) {
                        return open(request.getUrl().toString());
                    }

                    @Override
                    public boolean shouldOverrideUrlLoading(WebView child, String url) {
                        return open(url);
                    }
                });
                // Descarta também janelas que nunca recebem um destino.
                popup.postDelayed(popup::destroy, 15000);
                WebView.WebViewTransport transport =
                        (WebView.WebViewTransport) resultMsg.obj;
                transport.setWebView(popup);
                resultMsg.sendToTarget();
                return true;
            }
        });
    }
}
