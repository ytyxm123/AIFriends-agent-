import { createRouter, createWebHistory } from 'vue-router'
import HomepageIndex from "@/views/Homepage/HomepageIndex.vue";
import FriendIndex from "@/views/friends/FriendIndex.vue";
import CreateIndex from "@/views/create/CreateIndex.vue";
import LoginIndex from "@/views/user/account/LoginIndex.vue";
import RegisterIndex from "@/views/user/account/RegisterIndex.vue";
import NotFoundIndex from "@/views/error/NotFoundIndex.vue";
import ProfileIndex from "@/views/user/profile/ProfileIndex.vue";
import SpaceIndex from "@/views/user/space/SpaceIndex.vue";


const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [

    {
      path:'/',
      component:HomepageIndex,
      name:'homepage-index',
    },
    {
      path:'/friend/',
      component:FriendIndex,
      name:'Friend-index',
    },
    {
      path:'/create/',
      component:CreateIndex,
      name:'create-index',
    },
    {
      path:'/login/',
      component:LoginIndex,
      name:'login-index',
    },
    {
      path:'/register/',
      component:RegisterIndex,
      name:'register-index',
    },
    {
      path:'/NotFound/',
      component:NotFoundIndex,
      name:'home-page-index',
    },
    {
      path:'/profile/',
      component:ProfileIndex,
      name:'profile-index',
    },
    {
      path:'/space/:user_id/',
      component:SpaceIndex,
      name:'space-index',
    },
    {
      path:'/:pathMatch(.*)*',
      component:NotFoundIndex,
      name:'not-found',
    }
  ],
})

export default router
