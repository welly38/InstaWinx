from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'winx_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Inicializar banco de dados
def init_db():
    conn = sqlite3.connect('instawinx.db')
    c = conn.cursor()
    
    # Tabela de usuários
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  fairy_type TEXT,
                  profile_pic TEXT DEFAULT 'default_profile.png',
                  bio TEXT)''')
    
    # Tabela de posts
    c.execute('''CREATE TABLE IF NOT EXISTS posts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  image TEXT NOT NULL,
                  caption TEXT,
                  post_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    # Tabela de likes
    c.execute('''CREATE TABLE IF NOT EXISTS likes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  post_id INTEGER NOT NULL,
                  user_id INTEGER NOT NULL,
                  FOREIGN KEY (post_id) REFERENCES posts (id),
                  FOREIGN KEY (user_id) REFERENCES users (id),
                  UNIQUE(post_id, user_id))''')
    
    # Tabela de comentários
    c.execute('''CREATE TABLE IF NOT EXISTS comments
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  post_id INTEGER NOT NULL,
                  user_id INTEGER NOT NULL,
                  comment TEXT NOT NULL,
                  comment_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (post_id) REFERENCES posts (id),
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    # Tabela de amizades
    c.execute('''CREATE TABLE IF NOT EXISTS friendships
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user1_id INTEGER NOT NULL,
                  user2_id INTEGER NOT NULL,
                  status TEXT DEFAULT 'pending',
                  FOREIGN KEY (user1_id) REFERENCES users (id),
                  FOREIGN KEY (user2_id) REFERENCES users (id),
                  UNIQUE(user1_id, user2_id))''')
    
    conn.commit()
    conn.close()

init_db()

# Funções auxiliares do banco de dados
def get_db_connection():
    conn = sqlite3.connect('instawinx.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return user

def get_post_by_id(post_id):
    conn = get_db_connection()
    post = conn.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
    conn.close()
    return post

# Rotas principais
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Pegar posts de amigos
    user_id = session['user_id']
    posts = conn.execute('''
        SELECT p.*, u.username, u.profile_pic, u.fairy_type 
        FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.user_id = ? OR p.user_id IN (
            SELECT user2_id FROM friendships WHERE user1_id = ? AND status = 'accepted'
            UNION
            SELECT user1_id FROM friendships WHERE user2_id = ? AND status = 'accepted'
        )
        ORDER BY p.post_time DESC
    ''', (user_id, user_id, user_id)).fetchall()
    
    # Pegar likes e comentários para cada post
    posts_with_data = []
    for post in posts:
        post_dict = dict(post)
        
        # Likes
        likes = conn.execute('SELECT COUNT(*) FROM likes WHERE post_id = ?', (post['id'],)).fetchone()[0]
        post_dict['likes_count'] = likes
        
        # Verificar se o usuário atual curtiu
        user_liked = conn.execute('SELECT 1 FROM likes WHERE post_id = ? AND user_id = ?', 
                                (post['id'], user_id)).fetchone()
        post_dict['user_liked'] = bool(user_liked)
        
        # Comentários
        comments = conn.execute('''
            SELECT c.*, u.username, u.profile_pic 
            FROM comments c
            JOIN users u ON c.user_id = u.id
            WHERE c.post_id = ?
            ORDER BY c.comment_time
        ''', (post['id'],)).fetchall()
        post_dict['comments'] = [dict(comment) for comment in comments]
        
        posts_with_data.append(post_dict)
    
    # Sugestões de amigos (não amigos ainda)
    suggestions = conn.execute('''
        SELECT u.id, u.username, u.profile_pic, u.fairy_type 
        FROM users u
        WHERE u.id != ? AND u.id NOT IN (
            SELECT user2_id FROM friendships WHERE user1_id = ?
            UNION
            SELECT user1_id FROM friendships WHERE user2_id = ?
        )
        LIMIT 5
    ''', (user_id, user_id, user_id)).fetchall()
    
    conn.close()
    
    current_user = get_user_by_id(user_id)
    
    return render_template('feed.html', 
                         posts=posts_with_data, 
                         current_user=current_user,
                         suggestions=suggestions)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha incorretos', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        fairy_type = request.form['fairy_type']
        
        try:
            conn = get_db_connection()
            conn.execute('INSERT INTO users (username, password, fairy_type) VALUES (?, ?, ?)',
                         (username, password, fairy_type))
            conn.commit()
            conn.close()
            
            flash('Conta criada com sucesso! Faça login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Nome de usuário já existe', 'danger')
    
    fairy_types = ['Fada da Natureza', 'Fada do Fogo', 'Fada da Água', 
                  'Fada da Luz', 'Fada da Tecnologia', 'Fada da Música']
    return render_template('register.html', fairy_types=fairy_types)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Você saiu da sua conta', 'info')
    return redirect(url_for('login'))

@app.route('/create_post', methods=['POST'])
def create_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if 'image' not in request.files:
        flash('Nenhuma imagem selecionada', 'danger')
        return redirect(url_for('index'))
    
    image = request.files['image']
    caption = request.form.get('caption', '')
    
    if image.filename == '':
        flash('Nenhuma imagem selecionada', 'danger')
        return redirect(url_for('index'))
    
    if image:
        filename = f"{session['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        conn = get_db_connection()
        conn.execute('INSERT INTO posts (user_id, image, caption) VALUES (?, ?, ?)',
                     (session['user_id'], filename, caption))
        conn.commit()
        conn.close()
        
        flash('Post criado com sucesso!', 'success')
    
    return redirect(url_for('index'))

@app.route('/like_post/<int:post_id>', methods=['POST'])
def like_post(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Verificar se o usuário já curtiu
    already_liked = conn.execute('SELECT 1 FROM likes WHERE post_id = ? AND user_id = ?',
                                (post_id, session['user_id'])).fetchone()
    
    if already_liked:
        # Remover like
        conn.execute('DELETE FROM likes WHERE post_id = ? AND user_id = ?',
                     (post_id, session['user_id']))
    else:
        # Adicionar like
        conn.execute('INSERT INTO likes (post_id, user_id) VALUES (?, ?)',
                     (post_id, session['user_id']))
    
    conn.commit()
    
    # Contar likes atualizados
    likes_count = conn.execute('SELECT COUNT(*) FROM likes WHERE post_id = ?', (post_id,)).fetchone()[0]
    
    conn.close()
    
    return {'success': True, 'likes_count': likes_count, 'liked': not bool(already_liked)}

@app.route('/add_comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    comment = request.form.get('comment', '').strip()
    
    if comment:
        conn = get_db_connection()
        conn.execute('INSERT INTO comments (post_id, user_id, comment) VALUES (?, ?, ?)',
                     (post_id, session['user_id'], comment))
        conn.commit()
        
        # Pegar o comentário recém-adicionado com informações do usuário
        new_comment = conn.execute('''
            SELECT c.*, u.username, u.profile_pic 
            FROM comments c
            JOIN users u ON c.user_id = u.id
            WHERE c.id = last_insert_rowid()
        ''').fetchone()
        
        conn.close()
        
        return {'success': True, 'comment': dict(new_comment)}
    
    return {'success': False}

@app.route('/add_friend/<int:friend_id>', methods=['POST'])
def add_friend(friend_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    if user_id == friend_id:
        return {'success': False, 'error': 'Você não pode adicionar a si mesmo'}
    
    conn = get_db_connection()
    
    # Verificar se já existe uma solicitação
    existing = conn.execute('''
        SELECT * FROM friendships 
        WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)
    ''', (user_id, friend_id, friend_id, user_id)).fetchone()
    
    if existing:
        status = existing['status']
        if status == 'pending':
            if existing['user1_id'] == friend_id:
                # Aceitar solicitação pendente
                conn.execute('UPDATE friendships SET status = "accepted" WHERE id = ?', (existing['id'],))
                conn.commit()
                conn.close()
                return {'success': True, 'action': 'accepted'}
            else:
                # Solicitação já enviada
                conn.close()
                return {'success': False, 'error': 'Solicitação já enviada'}
        elif status == 'accepted':
            conn.close()
            return {'success': False, 'error': 'Já são amigos'}
    else:
        # Enviar nova solicitação
        conn.execute('INSERT INTO friendships (user1_id, user2_id) VALUES (?, ?)',
                     (user_id, friend_id))
        conn.commit()
        conn.close()
        return {'success': True, 'action': 'requested'}
    
    conn.close()
    return {'success': False}

@app.route('/profile/<username>')
def profile(username):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Pegar informações do perfil
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    
    if not user:
        conn.close()
        flash('Usuário não encontrado', 'danger')
        return redirect(url_for('index'))
    
    # Pegar posts do usuário
    posts = conn.execute('''
        SELECT p.*, 
               (SELECT COUNT(*) FROM likes WHERE post_id = p.id) as likes_count
        FROM posts p
        WHERE p.user_id = ?
        ORDER BY p.post_time DESC
    ''', (user['id'],)).fetchall()
    
    # Verificar status de amizade
    current_user_id = session['user_id']
    friendship_status = None
    
    if current_user_id != user['id']:
        friendship = conn.execute('''
            SELECT * FROM friendships 
            WHERE (user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?)
        ''', (current_user_id, user['id'], user['id'], current_user_id)).fetchone()
        
        if friendship:
            friendship_status = friendship['status']
            if friendship['user1_id'] == current_user_id and friendship_status == 'pending':
                friendship_status = 'request_sent'
            elif friendship['user2_id'] == current_user_id and friendship_status == 'pending':
                friendship_status = 'request_received'
    
    conn.close()
    
    current_user = get_user_by_id(current_user_id)
    
    return render_template('profile.html', 
                         user=user, 
                         posts=posts, 
                         current_user=current_user,
                         friendship_status=friendship_status)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)