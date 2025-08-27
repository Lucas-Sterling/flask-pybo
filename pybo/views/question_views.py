from datetime import datetime
from flask import Blueprint, render_template, request, url_for, g, flash
from werkzeug.utils import redirect
from .. import db
from ..models import Question, Answer, User, question_voter
from ..forms import QuestionForm, AnswerForm
from sqlalchemy import or_, func
from pybo.views.auth_views import login_required

bp = Blueprint('question', __name__, url_prefix='/question')

@bp.route('/list/')
def _list():
    # 입력 파라미터
    page = request.args.get('page', type=int, default=1)
    kw = (request.args.get('kw', type=str, default='') or '').strip()
    so = request.args.get('so', type=str, default='recent')

    # 기본 쿼리 (엔티티)
    question_list = Question.query

    # --- 검색 ---
    if kw:
        search = f'%{kw}%'
        # 답변 내용/작성자 검색용 서브쿼리
        subq_ans = (
            db.session.query(
                Answer.question_id.label('q_id'),
                Answer.content.label('a_content'),
                User.username.label('a_username')
            )
            .join(User, Answer.user_id == User.id)
            .subquery()
        )

        # 검색은 ID만 distinct 하여 서브쿼리로 뽑음 (DISTINCT + ORDER BY 충돌 회피)
        ids_subq = (
            db.session.query(Question.id)
            .join(User, Question.user_id == User.id)
            .outerjoin(subq_ans, subq_ans.c.q_id == Question.id)
            .filter(or_(
                Question.subject.ilike(search),        # 질문 제목
                Question.content.ilike(search),        # 질문 내용
                User.username.ilike(search),           # 질문 작성자
                subq_ans.c.a_content.ilike(search),    # 답변 내용
                subq_ans.c.a_username.ilike(search)    # 답변 작성자
            ))
            .distinct()
            .subquery()
        )

        # 엔티티 쿼리에 검색 결과(ID)만 반영
        question_list = question_list.filter(Question.id.in_(db.session.query(ids_subq.c.id)))

    # --- 정렬 ---
    if so == 'recommend':
        vote_subq = (
            db.session.query(
                question_voter.c.question_id.label('q_id'),
                func.count('*').label('num_voter')
            )
            .group_by(question_voter.c.question_id)
            .subquery()
        )
        question_list = (
            question_list
            .outerjoin(vote_subq, Question.id == vote_subq.c.q_id)
            # NULL 정렬 안전하게: 투표없음은 0으로 보고 내림차순
            .order_by(func.coalesce(vote_subq.c.num_voter, 0).desc(), Question.create_date.desc())
        )

    elif so == 'popular':
        ans_count_subq = (
            db.session.query(
                Answer.question_id.label('q_id'),
                func.count('*').label('num_answer')
            )
            .group_by(Answer.question_id)
            .subquery()
        )
        question_list = (
            question_list
            .outerjoin(ans_count_subq, Question.id == ans_count_subq.c.q_id)
            .order_by(func.coalesce(ans_count_subq.c.num_answer, 0).desc(), Question.create_date.desc())
        )

    else:  # 최신순
        question_list = question_list.order_by(Question.create_date.desc())

    # 페이징 (범위 벗어나도 404 안 나게)
    question_list = question_list.paginate(page=page, per_page=10, error_out=False)

    return render_template(
        'question/question_list.html',
        question_list=question_list,
        page=page,
        kw=kw,
        so=so
    )

@bp.route('/detail/<int:question_id>/')
def detail(question_id):
    form = AnswerForm()
    question = Question.query.get_or_404(question_id)
    return render_template('question/question_detail.html', question=question, form=form)

@bp.route('/create/', methods=('GET', 'POST'))
@login_required
def create():
    form = QuestionForm()
    if request.method == 'POST' and form.validate_on_submit():
        question = Question(
            subject=form.subject.data,
            content=form.content.data,
            create_date=datetime.now(),
            user=g.user
        )
        db.session.add(question)
        db.session.commit()
        return redirect(url_for('main.index'))
    return render_template('question/question_form.html', form=form)

@bp.route('/modify/<int:question_id>/', methods=('GET', 'POST'))
@login_required
def modify(question_id):
    question = Question.query.get_or_404(question_id)
    if g.user != question.user:
        flash('수정권한이 없습니다')
        return redirect(url_for('question.detail', question_id=question_id))

    if request.method == 'POST':
        form = QuestionForm()
        if form.validate_on_submit():
            form.populate_obj(question)
            question.modify_date = datetime.now()
            db.session.commit()
            return redirect(url_for('question.detail', question_id=question_id))
    else:
        form = QuestionForm(obj=question)
    return render_template('question/question_form.html', form=form)

@bp.route('/delete/<int:question_id>', methods=('POST',))
@login_required
def delete(question_id):
    question = Question.query.get_or_404(question_id)
    if g.user != question.user:
        flash('삭제권한이 없습니다')
        return redirect(url_for('question.detail', question_id=question_id))
    db.session.delete(question)
    db.session.commit()
    return redirect(url_for('question._list'))