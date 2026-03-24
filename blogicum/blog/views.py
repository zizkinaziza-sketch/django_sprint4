# blogicum/blog/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView, UpdateView, DeleteView, ListView, DetailView
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.db.models import Count
from .models import Post, Category, Comment
from .forms import PostForm, CommentForm
from django.contrib.auth import get_user_model

User = get_user_model()


def get_queryset_published():
    """Возвращает queryset опубликованных постов с датой публикации <= текущей даты"""
    return Post.objects.filter(
        is_published=True,
        category__is_published=True,
        pub_date__lte=timezone.now()
    ).select_related('author', 'location', 'category')


class IndexListView(ListView):
    model = Post
    template_name = 'blog/index.html'
    paginate_by = 10
    context_object_name = 'post_list'

    def get_queryset(self):
        return get_queryset_published().annotate(
            comment_count=Count('comments')
        ).order_by('-pub_date')


class CategoryPostsView(ListView):
    template_name = 'blog/category.html'
    paginate_by = 10
    context_object_name = 'post_list'

    def get_queryset(self):
        self.category = get_object_or_404(
            Category,
            slug=self.kwargs['category_slug'],
            is_published=True
        )
        return get_queryset_published().filter(
            category=self.category
        ).annotate(
            comment_count=Count('comments')
        ).order_by('-pub_date')


class ProfileListView(ListView):
    model = Post
    template_name = 'blog/profile.html'
    paginate_by = 10
    context_object_name = 'post_list'

    def get_queryset(self):
        self.profile_user = get_object_or_404(
            User,
            username=self.kwargs['username']
        )
        if self.request.user == self.profile_user:
            return Post.objects.filter(
                author=self.profile_user
            ).select_related(
                'location', 'category'
            ).annotate(
                comment_count=Count('comments')
            ).order_by('-pub_date')
        return get_queryset_published().filter(
            author=self.profile_user
        ).annotate(
            comment_count=Count('comments')
        ).order_by('-pub_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile'] = self.profile_user  # Добавляем profile в контекст
        return context


class PostDetailView(DetailView):
    model = Post
    template_name = 'blog/detail.html'
    pk_url_kwarg = 'post_id'
    context_object_name = 'post'

    def get_queryset(self):
        post = Post.objects.filter(
            id=self.kwargs['post_id']
        ).select_related('author', 'location', 'category')
        
        # Проверяем, существует ли пост
        if not post.exists():
            return post
        
        # Автор видит свой пост даже если он не опубликован
        if self.request.user.is_authenticated and self.request.user == post.first().author:
            return post.annotate(comment_count=Count('comments'))
        # Другие пользователи видят только опубликованные посты
        return post.filter(
            is_published=True,
            category__is_published=True,
            pub_date__lte=timezone.now()
        ).annotate(comment_count=Count('comments'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = CommentForm()
        # Сортировка комментариев от старых к новым (по created_at)
        context['comments'] = self.object.comments.select_related('author').order_by('created_at') if self.object else []
        return context


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    form = CommentForm(request.POST or None)
    
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
    
    return redirect('blog:post_detail', post_id=post_id)


@login_required
def edit_comment(request, post_id, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, post_id=post_id)
    
    if request.user != comment.author:
        return redirect('blog:post_detail', post_id=post_id)
    
    form = CommentForm(request.POST or None, instance=comment)
    
    if form.is_valid():
        form.save()
        return redirect('blog:post_detail', post_id=post_id)
    
    context = {
        'form': form,
        'comment': comment,
        'post_id': post_id
    }
    return render(request, 'blog/comment.html', context)


@login_required
def delete_comment(request, post_id, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, post_id=post_id)
    
    if request.user != comment.author:
        return redirect('blog:post_detail', post_id=post_id)
    
    if request.method == 'POST':
        comment.delete()
        return redirect('blog:post_detail', post_id=post_id)
    
    context = {
        'comment': comment,
        'post_id': post_id
    }
    return render(request, 'blog/comment_confirm_delete.html', context)


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('blog:profile', kwargs={'username': self.request.user.username})


class PostUpdateView(LoginRequiredMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'
    pk_url_kwarg = 'post_id'

    def dispatch(self, request, *args, **kwargs):
        post = self.get_object()
        if request.user != post.author:
            return redirect('blog:post_detail', post_id=post.id)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('blog:post_detail', kwargs={'post_id': self.object.id})


class PostDeleteView(LoginRequiredMixin, DeleteView):
    model = Post
    template_name = 'blog/create.html'
    pk_url_kwarg = 'post_id'
    success_url = reverse_lazy('blog:index')

    def dispatch(self, request, *args, **kwargs):
        post = self.get_object()
        if request.user != post.author:
            return redirect('blog:post_detail', post_id=post.id)
        return super().dispatch(request, *args, **kwargs)